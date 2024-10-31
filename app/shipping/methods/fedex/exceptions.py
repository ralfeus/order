class FedexItemsException(Exception):
    def __str__(self):
        return f"<FedexItemsException: {self.args}>"