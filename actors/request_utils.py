import flask.ext.restful.reqparse as reqparse
from werkzeug.exceptions import ClientDisconnected

TAG = '0.01'

class APIException(Exception):

    def __init__(self, message, code=400):
        Exception.__init__(self, message)
        self.message = message
        self.code = code
        self.status = 'error'
        self.tag = TAG

class RequestParser(reqparse.RequestParser):
    """Wrap reqparse to raise APIException."""

    def parse_args(self, *args, **kwargs):
        try:
            return super(RequestParser, self).parse_args(*args, **kwargs)
        except ClientDisconnected as exc:
            raise APIException(exc.data['message'], 400)

def ok(result, msg="The request was successful"):
    d = {'result': result,
         'status': 'success',
         'tag': TAG,
         'msg': msg}
    return d

def error(result=None, msg="Error processing your request."):
    d = {'result': result,
         'status': 'error',
         'tag': TAG,
         'msg': msg}
    return d