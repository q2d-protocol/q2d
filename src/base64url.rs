//! Base64url without padding — RFC 4648 §5 as RFC 7515 §2 uses it.
//!
//! Every segment of a JWS compact string is encoded this way, so this sits
//! under everything P-003 signs and verifies.
//!
//! ## What it refuses, and why refusing matters here
//!
//! A decoder that accepts more than one spelling of the same bytes is a
//! **malleability** surface, and one segment of a compact JWS is exposed to it.
//!
//! Re-spelling the header or the payload changes the signing input, so a
//! permissive decoder gains an attacker nothing there — verification fails on
//! its own. **The signature segment is the exception**: it is not an input to
//! anything, so a second spelling of the same 64 bytes verifies exactly as the
//! first does, while the `signed` string differs. `request_digest` is taken
//! over the exact `signed` bytes (`core-model.md` §6), so that is one exchange
//! with two digests, and a receipt that no longer matches the message anyone
//! holds.
//!
//! `suite/verify/respelled-signature-segment` is that case as a shared vector.
//!
//! So three refusals, none of them optional:
//!
//! - **Padding.** `=` is not in the encoding RFC 7515 §2 specifies. Accepting
//!   it would make `AAAA` and `AAAA=` the same message.
//! - **The standard alphabet.** `+` and `/` are RFC 4648 §4's, not §5's.
//! - **Non-canonical trailing bits.** A final group of two characters carries
//!   one byte and four spare bits; of three characters, two bytes and two
//!   spare. The spare bits must be zero. `QQ` and `QR` both decode to `A`
//!   under a permissive decoder, and that is the malleability above in its
//!   smallest form.
//!
//! A final group of **one** character is impossible: six bits cannot be a
//! byte. Rejected as a length error rather than silently dropped.
//!
//! ## Not a dependency
//!
//! Hand-written for the reason [`crate::digest`] is: this is a fixed
//! transformation with an exhaustive test, no secrets flow through it, and its
//! failure modes are the three above rather than anything cryptographic. That
//! reasoning does **not** extend to the curve arithmetic in P-003 issue 1 —
//! see `CONVENTIONS-rust.md`.

use std::fmt;

/// RFC 4648 §5's alphabet, in value order.
const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

/// Why a string is not base64url. Carries no decoded content — the input may be
/// a payload, and `core-model.md` §5.2 keeps values out of error text.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodeError(String);

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for DecodeError {}

/// Encode `bytes` as unpadded base64url.
pub fn encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let b = |i: usize| *chunk.get(i).unwrap_or(&0) as u32;
        let bits = (b(0) << 16) | (b(1) << 8) | b(2);
        // One output character per six bits, and one fewer group for each
        // byte the final chunk is short: 3 bytes → 4 characters, 2 → 3, 1 → 2.
        for i in 0..chunk.len() + 1 {
            out.push(ALPHABET[(bits >> (18 - 6 * i)) as usize & 0x3f] as char);
        }
    }
    out
}

/// Decode unpadded base64url, refusing every other spelling of the same bytes.
pub fn decode(text: &str) -> Result<Vec<u8>, DecodeError> {
    let bytes = text.as_bytes();
    if bytes.len() % 4 == 1 {
        // Six bits is not a byte and never was a byte. A decoder that dropped
        // this group would accept a string no encoder can produce.
        return Err(DecodeError(format!(
            "{} characters: a base64url group of one character encodes nothing",
            bytes.len()
        )));
    }

    let value = |c: u8| -> Result<u32, DecodeError> {
        ALPHABET
            .iter()
            .position(|&a| a == c)
            .map(|v| v as u32)
            .ok_or_else(|| match c {
                b'=' => DecodeError(
                    "padding, which RFC 7515 §2's encoding does not use — `AAAA` \
                     and `AAAA=` would otherwise be one message with two spellings"
                        .into(),
                ),
                b'+' | b'/' => DecodeError(
                    "a character from RFC 4648 §4's standard alphabet; §5's \
                     URL-safe alphabet uses `-` and `_`"
                        .into(),
                ),
                // Named by position, never by value: the input may be a payload.
                _ => DecodeError("a character outside RFC 4648 §5's alphabet".into()),
            })
    };

    let mut out = Vec::with_capacity(bytes.len() / 4 * 3);
    for chunk in bytes.chunks(4) {
        let mut bits = 0u32;
        for (i, &c) in chunk.iter().enumerate() {
            bits |= value(c)? << (18 - 6 * i);
        }
        // 4 characters → 3 bytes, 3 → 2, 2 → 1.
        for i in 0..chunk.len() - 1 {
            out.push((bits >> (16 - 8 * i)) as u8);
        }
        // Whatever the emitted bytes did not consume must have been zero. A
        // non-zero remainder is a second spelling of the bytes above it.
        //
        // The mask covers every bit below the last emitted byte; the bits
        // below the group itself are structurally zero, so it is the same
        // test. The *count* is not the mask width — a group of two characters
        // holds twelve bits and emits eight, so four are spare, and a group of
        // three holds eighteen and emits sixteen.
        if chunk.len() < 4 {
            let unconsumed = 8 * (4 - chunk.len());
            if bits & ((1 << unconsumed) - 1) != 0 {
                let spare = 6 * chunk.len() - 8 * (chunk.len() - 1);
                return Err(DecodeError(format!(
                    "{spare} trailing bits that are not zero, which is a \
                     second spelling of the same bytes"
                )));
            }
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    // RFC 4648 §10's test vectors, in §5's alphabet and without padding. The
    // published table is the standard alphabet with padding; these differ from
    // it only there, and no vector in it contains a byte that maps to `+` or
    // `/`, so the two agree character for character.
    const RFC4648: &[(&[u8], &str)] = &[
        (b"", ""),
        (b"f", "Zg"),
        (b"fo", "Zm8"),
        (b"foo", "Zm9v"),
        (b"foob", "Zm9vYg"),
        (b"fooba", "Zm9vYmE"),
        (b"foobar", "Zm9vYmFy"),
    ];

    #[test]
    fn rfc_4648_vectors_round_trip() {
        for (raw, encoded) in RFC4648 {
            assert_eq!(encode(raw), *encoded, "encoding {raw:?}");
            assert_eq!(decode(encoded).unwrap(), *raw, "decoding {encoded:?}");
        }
    }

    #[test]
    fn the_url_safe_alphabet_is_the_one_used() {
        // 0xFB 0xFF encodes to `-_` in §5 and `+/` in §4. The one input that
        // tells the two alphabets apart, so a decoder built on the wrong one
        // passes every other test here.
        assert_eq!(encode(&[0xfb, 0xff]), "-_8");
        assert_eq!(decode("-_8").unwrap(), vec![0xfb, 0xff]);
        assert!(decode("+/8").is_err());
    }

    #[test]
    fn padding_is_refused() {
        assert!(decode("Zg==").is_err());
        assert!(decode("Zm8=").is_err());
        // And the message says which problem it is, because a producer hitting
        // this has a one-line fix and no way to guess it from "invalid input".
        let message = decode("Zg==").unwrap_err().to_string();
        assert!(message.contains("padding"), "{message}");
    }

    #[test]
    fn non_canonical_trailing_bits_are_refused() {
        // `Zg` is `f`. `Zh` carries the same byte with a spare bit set, and a
        // permissive decoder returns `f` for both — one byte string, two
        // spellings, under a signature.
        assert_eq!(decode("Zg").unwrap(), b"f");
        assert!(decode("Zh").is_err());
        // Three characters: two spare bits rather than four.
        assert_eq!(decode("Zm8").unwrap(), b"fo");
        assert!(decode("Zm9").is_err());
    }

    #[test]
    fn a_group_of_one_character_is_refused() {
        assert!(decode("Z").is_err());
        assert!(decode("Zm9vZ").is_err());
    }

    #[test]
    fn whitespace_and_newlines_are_not_ignored() {
        // MIME base64 wraps at 76 columns and decoders often skip whitespace.
        // A JWS segment has none, and skipping it would accept a compact
        // string that is not the one that was signed.
        assert!(decode("Zm9v YmFy").is_err());
        assert!(decode("Zm9v\nYmFy").is_err());
        assert!(decode(" Zm9v").is_err());
    }

    #[test]
    fn every_byte_round_trips() {
        // Exhaustive over single bytes and over the 65 536 two-byte strings:
        // the encoder's shift arithmetic is where an off-by-one lives, and
        // these are the lengths whose final group is short.
        for a in 0u16..=255 {
            let one = [a as u8];
            assert_eq!(decode(&encode(&one)).unwrap(), one);
            for b in 0u16..=255 {
                let two = [a as u8, b as u8];
                assert_eq!(decode(&encode(&two)).unwrap(), two);
            }
        }
    }

    #[test]
    fn nothing_encodable_is_refused_by_the_decoder() {
        // The canonicalization check must not reject the encoder's own output.
        // A stricter-than-intended rule would show up here rather than as a
        // verification failure three modules away.
        for len in 0..64 {
            let raw: Vec<u8> = (0..len).map(|i| (i * 37 + 11) as u8).collect();
            assert_eq!(decode(&encode(&raw)).unwrap(), raw, "length {len}");
        }
    }

    #[test]
    fn no_error_message_carries_decoded_content() {
        // §5.2's rule reaches here: the input is a payload segment, and a
        // message naming the offending character would put one byte of it in a
        // log. Position is not carried either — it is a fact about the input.
        for bad in ["Zg==", "+/8", "Z", "Zh", "Zm9v YmFy", "Zm9v\u{00e9}"] {
            let message = decode(bad).unwrap_err().to_string();
            for c in bad.chars() {
                assert!(
                    !message.contains(&format!("'{c}'")) && !message.contains(&format!("{c:?}")),
                    "{bad}: {message}"
                );
            }
        }
    }
}
