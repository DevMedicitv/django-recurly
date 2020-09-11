
class PreVerificationTransactionRecurlyError(Exception):
    def __init__(self, transaction_error_code):
        self.transaction_error_code = transaction_error_code

    def __str__(self):
        return "InCorrect Payment Info, Pls recheck transaction_error_code: {}".format(self.transaction_error_code)