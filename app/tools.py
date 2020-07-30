''' Handful tools '''
import os
import os.path

__app_abs_dir_name = os.path.abspath(os.path.dirname(__file__))

# def get_free_file_name(path):
#     dir_name = os.path.dirname(os.path.join(__app_abs_dir_name, path))
#     free_path = os.path.basename(path)
#     i = 0
#     while os.path.exists(os.path.join(dir_name, free_path)):
#         free_path = f"{os.path.basename(path)}-{i}"
#         i += 1
#     return os.path.join(os.path.dirname(path), free_path)

def rm(path, not_exist_raise=False):
    abspath = os.path.join(__app_abs_dir_name, path)
    try:
        os.remove(abspath)
    except Exception as e:
        if not_exist_raise:
            raise e

def write_to_file(path, data):
    abspath = os.path.join(__app_abs_dir_name, path[1:])
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    with open(abspath, 'wb') as file:
        file.write(data)
        file.close()

