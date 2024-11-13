import unittest
import bpy

class TestQuickSetup(unittest.TestCase):
    def test_emission(self):
        bpy.ops.node.y_quick_ypaint_node_setup(type='EMISSION')
        
        nodes = bpy.data.materials['Material'].node_tree.nodes

        is_yp_node_found = False

        for node in nodes:
            if hasattr(node, 'node_tree'):
                is_yp_node_found = node.node_tree.yp.is_ypaint_node
            if is_yp_node_found == True: pass
        self.assertTrue(is_yp_node_found)