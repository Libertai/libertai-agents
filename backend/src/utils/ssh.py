import io

import paramiko


def generate_ssh_key_pair() -> tuple[str, str]:
    # Generate RSA key pair
    key = paramiko.RSAKey.generate(4096)

    # Serialize private key to string
    private_key_io = io.StringIO()
    key.write_private_key(private_key_io)
    private_key_str = private_key_io.getvalue()

    # Generate public key in OpenSSH format
    public_key_str = f"{key.get_name()} {key.get_base64()}"

    return private_key_str, public_key_str
