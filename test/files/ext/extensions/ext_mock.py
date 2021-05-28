from pkr.ext import ExtMixin


class ExtMock(ExtMixin):
    @staticmethod
    def get_context_template_data():
        return {"test": "Ok"}
