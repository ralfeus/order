class BuildPageNodesException(Exception):
    def __init__(self, node_id: str, ex: Exception):
        self.node_id = node_id
        self.ex = ex
    
    def __str__(self) -> str:
        return f"Thread {self.node_id}: {str(self.ex)}"