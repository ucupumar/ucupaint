from unittest import TestLoader, TestResult, TextTestRunner
from pathlib import Path
import bpy
from bpy.app.translations import pgettext_iface
from .common import *

def run_tests():
    test_loader = TestLoader()

    test_directory = str(Path(__file__).resolve().parent / 'tests')

    test_suite = test_loader.discover(test_directory, pattern='test_*.py')
    runner = TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    return result

def draw_test_ui(context, layout):
    wm = context.window_manager
    ypui = wm.ypui
    wmyp = wm.ypprops

    obj = context.object
    mat = get_active_material()
    node = get_active_ypaint_node()

    icon = 'TRIA_DOWN' if ypui.show_test else 'TRIA_RIGHT'
    row = layout.row(align=True)

    if is_bl_newer_than(2, 80):
        row.alignment = 'LEFT'
        row.scale_x = 0.95
        row.prop(ypui, 'show_test', emboss=False, text='Test', icon=icon)
    else:
        row.prop(ypui, 'show_test', emboss=False, text='', icon=icon)
        row.label(text='Test')

    if (ypui.show_test):
        box = layout.box()
        col = box.column()

        col.label(text='Run test with default cube scene!')
        if obj and obj.name == 'Cube' and mat and mat.name == 'Material' and not node:
            col.operator('wm.y_run_automated_test')

        if (wmyp.test_result_run != 0):
            col.label(text=pgettext_iface('Test Run Count: ') + str(wmyp.test_result_run))
            col.label(text=pgettext_iface('Test Error Count: ') + str(wmyp.test_result_error))
            col.label(text=pgettext_iface('Test Failed Count: ') + str(wmyp.test_result_failed))

class YRunAutomatedTest(bpy.types.Operator):
    bl_idname = "wm.y_run_automated_test"
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
