"""Binary protocol version of PCA9535 driver"""
import emulator_binary as eb

I2C_ADDR = 0x20

class PCA9535:
    def __init__(self, i2c):
        pass

    def read_all_pca9535_inputs(self):
        return eb.send_get_inputs()
