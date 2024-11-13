from unittest import TestLoader, TestResult, TextTestRunner
from pathlib import Path
import bpy

def run_tests():
    test_loader = TestLoader()

    test_directory = str(Path(__file__).resolve().parent / 'tests')

    test_suite = test_loader.discover(test_directory, pattern='test_*.py')
    runner = TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    return result


class YRunAutomatedTest(bpy.types.Operator):
    bl_idname = "node.y_run_automated_test"
    bl_label = "Run Automated Test"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        wm = context.window_manager
        wmyp = wm.ypprops

        # Reset test results
        wmyp.test_result_run = 0
        wmyp.test_result_error = 0
        wmyp.test_result_failed = 0

        # Run tests
        result = run_tests()

        # Set test results
        wmyp.test_result_run = result.testsRun
        wmyp.test_result_error = len(result.errors)
        wmyp.test_result_failed = len(result.failures)
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(YRunAutomatedTest)

def unregister():
    bpy.utils.unregister_class(YRunAutomatedTest)
