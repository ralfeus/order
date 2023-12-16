'''Structure of shipping next step'''
class ConsignResult:
    consignment_id: str
    next_step_message: str
    next_step_url: str

    def __init__(self, consignment_id: str, next_step_message: str, next_step_url: str):
        self.consignment_id = consignment_id
        self.next_step_message = next_step_message
        self.next_step_url = next_step_url

    def to_dict(self):
        return {
            'consignment_id': self.consignment_id,
            'message': self.next_step_message,
            'url': self.next_step_url
        }