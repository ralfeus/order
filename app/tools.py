''' Handful tools '''
import os
import os.path

def write_to_file(path, data):
    abspath = os.path.join(os.path.abspath(os.path.dirname(__file__)), path[1:])
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    with open(abspath, 'wb') as file:
        file.write(data)
        file.close()
