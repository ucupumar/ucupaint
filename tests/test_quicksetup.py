import unittest
import bpy

class TestQuickSetup(unittest.TestCase):
    def test_principled(self):

        # Quick Setup
        bpy.ops.node.y_quick_ypaint_node_setup(type='BSDF_PRINCIPLED')
        
        # Get yp
        yp = None
        nodes = bpy.data.materials['Material'].node_tree.nodes
        for node in nodes:
            if node.type == 'GROUP' and node.node_tree.yp.is_ypaint_node:
                yp = node.node_tree.yp
                
        self.assertTrue(yp != None)

        # Add new image layer
        bpy.ops.node.y_new_layer(name='Image', uv_map='UVMap')

        self.assertTrue(len(yp.layers) == 1)

        # Add new solid color layer with image mask
        bpy.ops.node.y_new_layer(name='Solid Color', type='COLOR', uv_map='UVMap', add_mask=True, mask_uv_name='UVMap')

        self.assertTrue(len(yp.layers) == 2)

