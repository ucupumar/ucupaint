
if "bpy" not in locals():
    from . import downloader
    from . import properties
    from . import operators
    from . import ui
else:
    import importlib
    importlib.reload(downloader)
    importlib.reload(properties)
    importlib.reload(operators)
    importlib.reload(ui)

def register():
    downloader.register()
    properties.register()
    operators.register()
    ui.register()

def unregister():
    downloader.unregister()
    properties.unregister()
    operators.unregister()
    ui.unregister()

if __name__ == "__main__":
    register()