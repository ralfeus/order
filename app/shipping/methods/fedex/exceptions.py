class FedexConfigurationException(Exception):
    pass

class FedexItemsException(Exception):
    def __str__(self):
        return f"<FedexItemsException: {self.args}>"
    
class FedexLoginException(Exception):
    pass