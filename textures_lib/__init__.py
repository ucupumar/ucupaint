
# if "bpy" not in locals():
from . import properties
from . import operators
from . import ui
# else:
#     import importlib

#     importlib.reload(properties)
#     importlib.reload(ui)
#     importlib.reload(operators)

def register():
    properties.register()
    operators.register()
    ui.register()

def unregister():
    properties.unregister()
    operators.unregister()
    ui.unregister()

if __name__ == "__main__":
    register()