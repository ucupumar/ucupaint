from unittest import TestLoader, TestResult, TextTestRunner
from pathlib import Path
import bpy

def run_tests():
    test_loader = TestLoader()

    test_directory = str(Path(__file__).resolve().parent / 'tests')

    test_suite = test_loader.discover(test_directory, pattern='test_*.py')
    runner = TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    print(result)


class YRunAutomatedTest(bpy.types.Operator):
    bl_idname = "node.y_run_autmated_test"
    bl_label = "Run Automated Test"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        run_tests()
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(YRunAutomatedTest.bl_idname, text=YRunAutomatedTest.bl_label)

def register():
    bpy.utils.register_class(YRunAutomatedTest)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.utils.unregister_class(YRunAutomatedTest)
    bpy.types.VIEW3D_MT_object.append(menu_func)