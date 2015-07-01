from flask import Flask, request
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

actors = []


class Actors(Resource):


    def get(self):
        result = []
        for x, actor in enumerate(actors):
            result.append({'id': x, 'image': actor['image']})
        return result

    def post(self):
        image = request.form['image']
        actors.append({'image': image})
        id = len(actors) - 1
        return {'id': id, 'image':image}

api.add_resource(Actors, '/actors')

if __name__ == '__main__':
    app.run(debug=True)