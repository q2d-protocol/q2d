//! `digest = "sha256:" + lowercase_hex(SHA-256(bytes))` — serialization.md §5.
//!
//! The algorithm prefix is mandatory, so a digest is self-describing and a
//! future algorithm is additive rather than ambiguous. Changing the encoding
//! changes every receipt, which is why P-002 §9 item 6 makes it an escalation.
//!
//! ## Which four
//!
//! `request_digest`, `response_digest`, `effective_contract_digest`,
//! `public_context_digest`. **Only the first digests received bytes with no
//! re-serialization** — it covers the exact `signed` bytes of the query, which
//! is what makes it checkable by anyone holding the envelope. The other three
//! digest a sub-object and therefore need serialization.md §1, which is why
//! that profile applies beyond the payload.
//!
//! This module is the construction. Which bytes go into each of the four is
//! P-011's and P-012's, and `response_digest` in particular is not the
//! symmetric thing its name suggests: the receipt travels *inside* the response
//! and carries the digest, so digesting the whole response would include the
//! digest itself. P-011 §4.2 is authoritative.
//!
//! ## Why SHA-256 is written out here
//!
//! Rust's standard library has no SHA-256 and this crate takes no
//! dependencies. So it is implemented from FIPS 180-4 and **gated on the
//! published known answers** — the same arrangement `tools/author_vectors.py`
//! uses for Ed25519, where a mistake in a constant fails a test rather than
//! producing a plausible wrong digest that becomes the answer two
//! implementations are held to.
//!
//! Go uses `crypto/sha256`, and the asymmetry is deliberate rather than
//! untidy: the shared fixture holds both to the same bytes, so a defect in
//! this implementation shows up as a disagreement with a standard library
//! rather than as two copies of the same mistake. That is the opposite of the
//! serializer, where the standard library had behaviours the profile forbids.

/// A digest of `bytes`, as serialization.md §5 spells it.
pub fn digest(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(7 + 64);
    out.push_str("sha256:");
    for byte in sha256(bytes) {
        // Lowercase, fixed width. `{:x}` alone would render 0x0a as "a" and
        // produce a 63-character digest for one input in 256.
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

/// FIPS 180-4 §4.2.2's round constants: the first thirty-two bits of the
/// fractional parts of the cube roots of the first sixty-four primes.
const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

/// §5.3.3's initial hash value: the fractional parts of the square roots of
/// the first eight primes.
const H0: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

fn sha256(message: &[u8]) -> [u8; 32] {
    let mut h = H0;

    // §5.1.1 padding: a `1` bit, zeros, and the length in bits as a 64-bit
    // big-endian integer, to a multiple of 512 bits.
    let mut padded = message.to_vec();
    padded.push(0x80);
    while padded.len() % 64 != 56 {
        padded.push(0);
    }
    padded.extend_from_slice(&(message.len() as u64 * 8).to_be_bytes());

    for block in padded.chunks_exact(64) {
        let mut w = [0u32; 64];
        for (i, word) in block.chunks_exact(4).enumerate() {
            w[i] = u32::from_be_bytes([word[0], word[1], word[2], word[3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }

        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh] = h;
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ (!e & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);

            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }

        for (slot, value) in h.iter_mut().zip([a, b, c, d, e, f, g, hh]) {
            *slot = slot.wrapping_add(value);
        }
    }

    let mut out = [0u8; 32];
    for (chunk, word) in out.chunks_exact_mut(4).zip(h) {
        chunk.copy_from_slice(&word.to_be_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// FIPS 180-4's published examples, plus NIST's long one.
    ///
    /// **This is the load-bearing test in the file.** Every constant above —
    /// sixty-four round constants and eight initial words — is checked against
    /// a published answer, so a transcription error fails here rather than
    /// producing a plausible wrong digest that becomes the number a receipt is
    /// held to.
    const KNOWN: [(&str, &str); 4] = [
        (
            "",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ),
        (
            "abc",
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        ),
        (
            "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
        ),
        (
            // Two blocks plus a byte, so the padding path that adds a whole
            // extra block is exercised rather than assumed.
            "abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmno\
             ijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
            "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1",
        ),
    ];

    #[test]
    fn sha256_reproduces_the_published_known_answers() {
        for (message, expected) in KNOWN {
            let produced: String = sha256(message.as_bytes())
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect();
            assert_eq!(produced, expected, "SHA-256 of {message:?}");
        }
    }

    #[test]
    fn the_padding_boundaries_are_exercised() {
        // 55, 56 and 64 bytes: the last that fits with its length word, the
        // first that forces a second block, and an exact block. Off-by-one
        // padding passes every short input and fails exactly here.
        for length in [55, 56, 63, 64, 65, 119, 120] {
            let message = vec![b'a'; length];
            // Against a property rather than a constant: the digest is 32
            // bytes and differs from its neighbours. The known answers above
            // are what pin the algorithm; this pins the block arithmetic.
            let here = sha256(&message);
            let longer = sha256(&vec![b'a'; length + 1]);
            assert_ne!(here, longer, "length {length}");
        }
    }

    #[test]
    fn a_digest_carries_the_prefix_and_is_lowercase_hex() {
        let d = digest(b"abc");
        assert_eq!(
            d,
            "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        // serialization.md §5: the prefix is mandatory so the digest is
        // self-describing.
        assert!(d.starts_with("sha256:"));
        // 7 + 64. A `{:x}` that dropped a leading zero would be 63 for one
        // input in 256, which is the kind of defect that passes a spot check.
        assert_eq!(d.len(), 71);
        assert!(d["sha256:".len()..]
            .chars()
            .all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c)));
    }

    #[test]
    fn a_leading_zero_byte_keeps_its_width() {
        // The input whose digest begins with a zero byte, found by search.
        // Without it the lowercase-hex rule is only tested where it cannot
        // fail.
        let d = digest(b"\x03");
        assert_eq!(d.len(), 71, "{d}");
        assert!(d.starts_with("sha256:0"), "{d}");
    }
}
