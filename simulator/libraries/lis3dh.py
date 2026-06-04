class LIS3DH_I2C:
    def __init__(self, *args, **kwargs):
        print("FAKE LIS3DH_I2C initialized with args:", args, "and kwargs:", kwargs)
        self.acceleration = Acceleration(0.0, 0.0, 0.0)
    
class Acceleration:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
