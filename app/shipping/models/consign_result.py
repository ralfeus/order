'''Structure of shipping next step'''
class ConsignResult:
    tracking_id: str
    next_step_message: str
    next_step_url: str

    def __init__(self, tracking_id: str, next_step_message: str='', 
                 next_step_url: str=''):
        self.tracking_id = tracking_id
        self.next_step_message = next_step_message
        self.next_step_url = next_step_url

    def to_dict(self):
        return {
            'tracking_id': self.tracking_id,
            'message': self.next_step_message,
            'url': self.next_step_url
        }