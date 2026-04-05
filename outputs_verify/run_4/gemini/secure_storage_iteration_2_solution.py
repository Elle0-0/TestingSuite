import os
import hmac
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

# --- Configuration Constants ---
SALT_SIZE = 16
IV_SIZE = 16  # AES block size is 128 bits
HMAC_SIZE = 32  # SHA-256 output size
KEY_SIZE = 32  # For AES-256
PBKDF2_ITERATIONS = 480000  # Number of iterations for key derivation

class IntegrityCheckFailed(Exception):
    """Custom exception raised for HMAC mismatch or decryption errors."""
    pass

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.

    The file format is: salt || iv || hmac || ciphertext
    """
    salt = os.urandom(SALT_SIZE)

    # Derive separate encryption and MAC keys from the passphrase and salt
    derived_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE + HMAC_SIZE
    )
    enc_key = derived_key[:KEY_SIZE]
    mac_key = derived_key[KEY_SIZE:]

    # Pad data to be a multiple of the AES block size
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data.encode('utf-8')) + padder.finalize()

    # Generate a random Initialization Vector (IV)
    iv = os.urandom(IV_SIZE)

    # Encrypt the data
    cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Create an HMAC for integrity check (on iv + ciphertext)
    # This is an "Encrypt-then-MAC" approach
    mac = hmac.new(mac_key, iv + ciphertext, hashlib.sha256)
    hmac_digest = mac.digest()

    # Write all parts to the file
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(iv)
        f.write(hmac_digest)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves, verifies, and decrypts data from a file.

    Raises IntegrityCheckFailed if the passphrase is wrong or the file is corrupted.
    """
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            iv = f.read(IV_SIZE)
            hmac_from_file = f.read(HMAC_SIZE)
            ciphertext = f.read()

        # Check for a truncated file
        if len(salt) != SALT_SIZE or len(iv) != IV_SIZE or len(hmac_from_file) != HMAC_SIZE:
            raise IntegrityCheckFailed("File is corrupted or has an invalid format.")

        # Re-derive the keys using the salt from the file
        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            PBKDF2_ITERATIONS,
            dklen=KEY_SIZE + HMAC_SIZE
        )
        enc_key = derived_key[:KEY_SIZE]
        mac_key = derived_key[KEY_SIZE:]

        # Verify the HMAC
        calculated_hmac = hmac.new(mac_key, iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(hmac_from_file, calculated_hmac):
            raise IntegrityCheckFailed("Integrity check failed: file may be corrupted or passphrase is wrong.")

        # If HMAC is valid, proceed with decryption
        cipher = Cipher(algorithms.AES(enc_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Unpad the decrypted data
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

        return plaintext.decode('utf-8')

    except FileNotFoundError:
        # Let this specific, common error bubble up as is.
        raise
    except (ValueError, IndexError) as e:
        # Catches bad padding (ValueError), bad slicing from a malformed file (IndexError), etc.
        # These errors indicate corruption or a wrong key.
        raise IntegrityCheckFailed("Decryption failed: file may be corrupted or passphrase is wrong.") from e
    except IntegrityCheckFailed:
        # Re-raise our explicitly raised exception.
        raise

def main():
    """Demonstrates the secure storage and retrieval system."""
    FILE = "my_secret_data.bin"
    CORRUPTED_FILE = "corrupted_data.bin"
    PASSPHRASE = "correct horse battery staple"
    WRONG_PASSPHRASE = "incorrect donkey battery staple"
    DATA = "The crow flies at midnight."

    # --- 1. Successful storage and retrieval ---
    print("--- 1. Testing successful storage and retrieval ---")
    try:
        store_file(FILE, DATA, PASSPHRASE)
        print(f"File '{FILE}' stored successfully.")
        retrieved_data = retrieve_file(FILE, PASSPHRASE)
        print(f"File '{FILE}' retrieved successfully.")
        print(f"Original data:    '{DATA}'")
        print(f"Retrieved data:   '{retrieved_data}'")
        assert DATA == retrieved_data
        print("Success: Data matches.\n")
    except Exception as e:
        print(f"An unexpected error occurred: {type(e).__name__}: {e}\n")

    # --- 2. Failed attempt with wrong passphrase ---
    print("--- 2. Testing retrieval with wrong passphrase ---")
    try:
        print(f"Attempting to retrieve '{FILE}' with a wrong passphrase...")
        retrieve_file(FILE, WRONG_PASSPHRASE)
        print("Failure: Exception was not raised for wrong passphrase.")
    except IntegrityCheckFailed:
        print("Success: Caught expected exception.")
        print("The system correctly prevented access due to a wrong passphrase or file corruption.\n")
    except Exception as e:
        print(f"Failure: Caught an unexpected exception: {type(e).__name__}: {e}\n")

    # --- 3. Failed attempt with a corrupted file ---
    print("--- 3. Testing retrieval of a corrupted file ---")
    try:
        # Create a corrupted copy of the file by tampering with it
        with open(FILE, 'rb') as f:
            original_content = f.read()
        
        # Tamper with the ciphertext (flip a bit in the middle)
        corrupted_content = bytearray(original_content)
        tamper_index = len(corrupted_content) - 10
        if tamper_index > 0:
            corrupted_content[tamper_index] ^= 0x01
        
        with open(CORRUPTED_FILE, 'wb') as f:
            f.write(corrupted_content)
        print(f"Created a corrupted file: '{CORRUPTED_FILE}'")

        print(f"Attempting to retrieve '{CORRUPTED_FILE}' with the correct passphrase...")
        retrieve_file(CORRUPTED_FILE, PASSPHRASE)
        print("Failure: Exception was not raised for corrupted file.")
    except IntegrityCheckFailed:
        print("Success: Caught expected exception.")
        print("The system correctly identified that the file has been tampered with.\n")
    except Exception as e:
        print(f"Failure: Caught an unexpected exception: {type(e).__name__}: {e}\n")

    # --- Cleanup ---
    finally:
        print("--- Cleanup ---")
        for f in [FILE, CORRUPTED_FILE]:
            if os.path.exists(f):
                os.remove(f)
                print(f"Removed '{f}'.")

if __name__ == "__main__":
    main()