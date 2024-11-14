import unittest, os
import bpy

def get_yp():
    yp = None
    nodes = bpy.data.materials['Material'].node_tree.nodes
    for node in nodes:
        if node.type == 'GROUP' and node.node_tree.yp.is_ypaint_node:
            yp = node.node_tree.yp

    return yp

def get_active_layer():
    yp = get_yp()
    return yp.layers[yp.active_layer_index]

def get_texdir():
    filepath = os.path.realpath(__file__)
    dirname = os.path.dirname(filepath) 
    return dirname + os.sep + 'textures'

class TestPrincipled(unittest.TestCase):
    def test_00_principled(self):
        # Quick Setup
        bpy.ops.node.y_quick_ypaint_node_setup(type='BSDF_PRINCIPLED')
        
        # Get yp
        yp = get_yp()
        self.assertTrue(yp != None)

    def test_99_remove_yp_node(self):
        bpy.ops.node.y_remove_yp_node()

        # Get yp
        yp = get_yp()
        self.assertTrue(yp == None)

class TestNewLayer(TestPrincipled):
    def test_01_new_layer(self):
        # Add new image layer
        bpy.ops.node.y_new_layer(name='Image', uv_map='UVMap')

        yp = get_yp()
        self.assertTrue(len(yp.layers) == 1)

class TestNewLayerWithMask(TestPrincipled):
    def test_01_new_layer_with_mask(self):
        # Add new solid color layer with image mask
        bpy.ops.node.y_new_layer(name='Solid Color', type='COLOR', uv_map='UVMap', add_mask=True, mask_uv_name='UVMap')

        yp = get_yp()
        self.assertTrue(len(yp.layers) == 1)

class TestOpenImageAsLayer(TestPrincipled):
    def test_01_open_image_to_layer(self):
        texdir = get_texdir()

        # Open image as layer
        bpy.ops.node.y_open_image_to_layer(
            files = [{"name":"blender_color.png"}], 
            directory = texdir,
            uv_map="UVMap"
        )
        
        yp = get_yp()
        self.assertTrue(len(yp.layers) == 1)

class TestOpenImagesToSingleLayerWithMask(TestPrincipled):
    def test_01_open_images_to_single_layer_with_mask(self):
        texdir = get_texdir()

        # Open images to single layer with white mask
        bpy.ops.node.y_open_images_to_single_layer(
            files = [
                {"name":"blender_color.png"},
                {"name":"blender_metallic.png"},
                {"name":"blender_roughness.png"}, 
                {"name":"blender_bump.png"} 
            ], 
            directory = texdir, 
            uv_map = "UVMap",
            add_mask = True,
            mask_uv_name = 'UVMap',
            mask_color = 'WHITE'
        )
        
        yp = get_yp()
        self.assertTrue(len(yp.layers) == 1)

class TestNewMask(TestOpenImageAsLayer):
    def test_02_new_mask(self):

        # New layer mask
        bpy.ops.node.y_new_layer_mask(name='Image Mask', uv_name='UVMap', color_option='WHITE')

        layer = get_active_layer()
        self.assertTrue(len(layer.masks) == 1)

class TestEnableNormal(TestNewMask):
    def test_03_enable_normal(self):
        layer = get_active_layer()

        # Enable normal channel (it use index 3 by default)
        layer.channels[3].enable = True

        # TODO: Need proper state for this
        self.assertTrue(True)

class TestEnableTransitionBump(TestEnableNormal):
    def test_04_enable_transition_bump(self):
        layer = get_active_layer()

        # Show and enable transition bump
        layer.channels[3].show_transition_bump = True
        layer.channels[3].enable_transition_bump = True

        # TODO: Need proper state for this
        self.assertTrue(True)

class TestDuplicateLayer(TestNewLayer):
    def test_02_duplicate_layer(self):

        # Duplicate Layer
        bpy.ops.node.y_duplicate_layer()

        yp = get_yp()
        self.assertTrue(len(yp.layers) == 2)
