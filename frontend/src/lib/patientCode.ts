/**
 * Patient codes, the same algorithm as backend/app/core/patient_codes.py.
 *
 * Format PHC-XXXXXC: five random characters plus a Luhn mod N check character. The alphabet leaves out
 * characters that are easy to confuse on a handwritten card (0/O, 1/I/L, U), and has an even size (30)
 * so the check catches every single wrong character. The device generates the code, so a patient gets
 * one even offline; the server keeps it when it is free and enforces uniqueness.
 */
export const ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ";
export const PREFIX = "PHC-";
const BODY_LENGTH = 5;
const N = ALPHABET.length;
const PATTERN = new RegExp(`^${PREFIX}[${ALPHABET}]{${BODY_LENGTH + 1}}$`);

function luhnSum(chars: string, doubleFirst: boolean): number {
  let total = 0;
  let double = doubleFirst;
  for (let i = chars.length - 1; i >= 0; i -= 1) {
    const addend = ALPHABET.indexOf(chars.charAt(i)) * (double ? 2 : 1);
    total += Math.floor(addend / N) + (addend % N);
    double = !double;
  }
  return total;
}

export function checkCharacter(body: string): string {
  return ALPHABET.charAt((N - (luhnSum(body, true) % N)) % N);
}

export function isValidPatientCode(code: string): boolean {
  const normalised = code.trim().toUpperCase();
  return PATTERN.test(normalised) && luhnSum(normalised.slice(PREFIX.length), false) % N === 0;
}

export function generatePatientCode(random: (max: number) => number = secureRandomInt): string {
  let body = "";
  for (let i = 0; i < BODY_LENGTH; i += 1) body += ALPHABET.charAt(random(N));
  return `${PREFIX}${body}${checkCharacter(body)}`;
}

function secureRandomInt(max: number): number {
  // Rejection sampling keeps every character equally likely.
  const limit = Math.floor(256 / max) * max;
  const byte = new Uint8Array(1);
  let value: number;
  do {
    crypto.getRandomValues(byte);
    value = byte[0] ?? 255;
  } while (value >= limit);
  return value % max;
}
