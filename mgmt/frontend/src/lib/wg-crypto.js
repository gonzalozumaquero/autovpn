import sodium from "libsodium-wrappers";

export async function genWGKeypair() {
  await sodium.ready;
  const sk = sodium.randombytes_buf(32);
  const pk = sodium.crypto_scalarmult_base(sk);
  return {
    privateKey: sodium.to_base64(sk, sodium.base64_variants.ORIGINAL),
    publicKey: sodium.to_base64(pk, sodium.base64_variants.ORIGINAL)
  };
}
