import os
from pymt5linux import MetaTrader5
from dotenv import load_dotenv

load_dotenv()


def test_rpyc_connection():
    mt5_login = int(os.getenv("MT5_ACCOUNT"))
    mt5_password = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    mt5_host = os.getenv("MT5_RPYC_HOST")
    mt5_port = int(os.getenv("MT5_RPYC_PORT"))

    print("Establishing connection...")
    mt5 = MetaTrader5(host=mt5_host, port=mt5_port)

    print("===== Your Credential =====")
    print(f"Login: {mt5_login}\n")
    print(f"Password: {mt5_password}\n")
    print(f"Server: {mt5_server}\n")
    print(f"RPyC host: {mt5_host}\n")
    print(f"RPyC port: {mt5_port}\n")

    print("Initialize MetaTrader5 terminal...")
    if not mt5.initialize(login=mt5_login, password=mt5_password, server=mt5_server):
        print(f"Initialize() failed, error code = {mt5.last_error()}")
        quit()

    print(f"===== Your Terminal =====")
    print(f"Terminal info: {mt5.terminal_info()}\n")
    print(f"Account info: {mt5.account_info()}\n")
    print("Closing connection...")
    mt5.shutdown()


if __name__ == "__main__":
    test_rpyc_connection()
