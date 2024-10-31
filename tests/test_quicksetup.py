import unittest
import bpy

class TestQuickSetup(unittest.TestCase):
    def test_emission(self):
        bpy.ops.node.y_quick_ypaint_node_setup(type='EMISSION')
        
        nodes = bpy.data.materials['Material'].node_tree.nodes

        ucupaint = False

        for node in nodes:
            if hasattr(node, 'node_tree'):
                ucupaint = node.node_tree.yp.is_ypaint_node
            if ucupaint == True: pass
        self.assertTrue(ucupaint)