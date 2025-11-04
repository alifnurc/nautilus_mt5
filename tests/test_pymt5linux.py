from pymt5linux import MetaTrader5

print("Establishing connection...")
mt5 = MetaTrader5(host="localhost", port=18847)

mt5.initialize()

print("Closing connection...")
mt5.shutdown()
