/* ==========================================================================
   SafeLife — vault cryptography (runs entirely in the browser)

   * Key:       PBKDF2-SHA256 (600,000 iterations) from the vault passphrase + a
                per-account random salt that the server stores (salt is not secret).
   * Cipher:    AES-256-GCM with a fresh random 12-byte IV for every encryption.
                GCM is authenticated: a wrong key or tampered data fails to decrypt.
   * Keys are non-extractable CryptoKey objects, kept in memory only.
   * The server only ever sees base64 ciphertext.

   Uses the Web Crypto API, which needs a secure context: https:// or localhost.
   ========================================================================== */
window.VaultCrypto = (() => {
  const ITERATIONS = 600000;
  const IV_BYTES = 12;
  const CHECK_TEXT = "safelife-vault-check-v1";
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const b64 = {
    encode(bytes) {
      let s = "";
      const CHUNK = 0x8000;
      for (let i = 0; i < bytes.length; i += CHUNK) {
        s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
      }
      return btoa(s);
    },
    decode(str) {
      const bin = atob(str);
      const out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    },
  };

  /** Derive the AES-GCM key from the passphrase and the account salt. */
  async function deriveKey(passphrase, saltB64) {
    const base = await crypto.subtle.importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt: b64.decode(saltB64), iterations: ITERATIONS, hash: "SHA-256" },
      base,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"]
    );
  }

  /** Encrypt raw bytes. Output = base64(iv || ciphertext). */
  async function sealBytes(key, bytes) {
    const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes));
    const out = new Uint8Array(IV_BYTES + ct.length);
    out.set(iv, 0);
    out.set(ct, IV_BYTES);
    return b64.encode(out);
  }

  /** Decrypt base64(iv || ciphertext). Throws if the key is wrong or data was altered. */
  async function openBytes(key, packed) {
    const data = b64.decode(packed);
    if (data.length <= IV_BYTES) throw new Error("ciphertext too short");
    const iv = data.subarray(0, IV_BYTES);
    const ct = data.subarray(IV_BYTES);
    return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct));
  }

  const sealJSON = (key, obj) => sealBytes(key, enc.encode(JSON.stringify(obj)));
  const openJSON = async (key, packed) => JSON.parse(dec.decode(await openBytes(key, packed)));

  /** A known value encrypted with the key, stored once so we can check the passphrase later. */
  const makeCheck = (key) => sealBytes(key, enc.encode(CHECK_TEXT));
  async function verifyCheck(key, check) {
    try {
      return dec.decode(await openBytes(key, check)) === CHECK_TEXT;
    } catch (_) {
      return false;
    }
  }

  return {
    ITERATIONS,
    deriveKey,
    sealBytes,
    openBytes,
    sealJSON,
    openJSON,
    makeCheck,
    verifyCheck,
    b64,
  };
})();
