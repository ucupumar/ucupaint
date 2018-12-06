import bpy
from bpy.props import *
from mathutils import *
from .common import *
from .node_connections import *
from .node_arrangements import *
from . import lib

def prepare_bake_settings(self, context):
    scene = self.scene
    obj = self.obj
    uv_layers = self.uv_layers

    # Remember render settings
    self.ori_engine = scene.render.engine
    self.ori_bake_type = scene.cycles.bake_type
    self.ori_samples = scene.cycles.samples
    self.ori_threads_mode = scene.render.threads_mode
    self.ori_margin = scene.render.bake.margin
    self.ori_use_clear = scene.render.bake.use_clear

    # Remember nodes
    #self.ori_active_node = 

    # Remember scene objects
    self.ori_active_obj = scene.objects.active
    self.ori_active_selected_objs = [o for o in scene.objects if o.select]

    scene.render.engine = 'CYCLES'
    scene.cycles.bake_type = 'EMIT'
    scene.cycles.samples = self.samples
    scene.render.threads_mode = 'AUTO'
    scene.render.bake.margin = self.margin
    #scene.render.bake.use_clear = True
    scene.render.bake.use_clear = False

    # Disable other object selections
    for o in scene.objects:
        o.select = False

    # Select object
    scene.objects.active = obj
    obj.select = True

    # Remember uv
    self.ori_active_uv = uv_layers.active

    # Set active uv layers
    uv_layers.active = uv_layers.get(self.uv_map)

def recover_bake_settings(self, context):
    scene = self.scene
    obj = self.obj
    uv_layers = self.uv_layers

    scene.render.engine = self.ori_engine
    scene.cycles.bake_type = self.ori_bake_type
    scene.cycles.samples = self.ori_samples
    scene.render.threads_mode = self.ori_threads_mode
    scene.render.bake.margin = self.ori_margin
    scene.render.bake.use_clear = self.ori_use_clear

    # Recover uv
    uv_layers.active = self.ori_active_uv

    # Disable other object selections
    for o in scene.objects:
        if o in self.ori_active_selected_objs:
            o.select = True
        else: o.select = False

    # Recover active object
    scene.objects.active = self.ori_active_obj

class YBakeChannels(bpy.types.Operator):
    """Bake Channels to Image(s)"""
    bl_idname = "node.y_bake_channels"
    bl_label = "Bake channels to Image"
    bl_options = {'REGISTER', 'UNDO'}

    width = IntProperty(name='Width', default = 1024, min=1, max=4096)
    height = IntProperty(name='Height', default = 1024, min=1, max=4096)

    uv_map = StringProperty(default='')
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    samples = IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1)

    margin = IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object.type == 'MESH'

    def invoke(self, context, event):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        obj = self.obj = context.object
        scene = self.scene = context.scene

        # Use active uv layer name by default
        if hasattr(obj.data, 'uv_textures'):
            uv_layers = self.uv_layers = obj.data.uv_textures
        else: uv_layers = self.uv_layers = obj.data.uv_layers

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(uv_layers) > 0:
            active_name = uv_layers.active.name
            if active_name == TEMP_UV:
                self.uv_map = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_map = uv_layers.active.name

            # UV Map collections update
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        if bpy.app.version_string.startswith('2.8'):
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)
        col = row.column(align=True)

        col.label(text='Width:')
        col.label(text='Height:')
        col.separator()
        col.label(text='Samples:')
        col.label(text='Margin:')
        col.separator()
        col.label(text='UV Map:')

        col = row.column(align=True)

        col.prop(self, 'width', text='')
        col.prop(self, 'height', text='')
        col.separator()

        col.prop(self, 'samples', text='')
        col.prop(self, 'margin', text='')
        col.separator()

        col.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

    def execute(self, context):

        mat = get_active_material()
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp

        # Disable use baked first
        if yp.use_baked:
            yp.use_baked = False

        # Prepare bake settings
        prepare_bake_settings(self, context)

        # Create nodes
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        emit = mat.node_tree.nodes.new('ShaderNodeEmission')

        #linear = mat.node_tree.nodes.new('ShaderNodeGamma')
        #linear.inputs['Gamma'].default_value = GAMMA
        linear = mat.node_tree.nodes.new('ShaderNodeGroup')
        linear.node_tree = get_node_tree_lib(lib.SRGB_2_LINEAR)

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL)

        # Set tex as active node
        mat.node_tree.nodes.active = tex

        # Get output node and remember original bsdf input
        output = get_active_mat_output_node(mat.node_tree)
        ori_bsdf = output.inputs[0].links[0].from_socket

        # Connect emit to output material
        mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

        for ch in yp.channels:

            # Set nodes
            baked = tree.nodes.get(ch.baked)
            if not baked:
                baked = new_node(tree, ch, 'baked', 'ShaderNodeTexImage', 'Baked ' + ch.name)
            if ch.colorspace == 'LINEAR' or ch.type == 'NORMAL':
                baked.color_space = 'NONE'
            else: baked.color_space = 'COLOR'
            
            # Get uv map
            uv = tree.nodes.get(BAKED_UV)
            if not uv:
                uv = tree.nodes.new('ShaderNodeUVMap')
                uv.name = BAKED_UV

            # Set uv map
            uv.uv_map = self.uv_map

            # Normal related nodes
            if ch.type == 'NORMAL':
                baked_normal = tree.nodes.get(ch.baked_normal)
                if not baked_normal:
                    baked_normal = new_node(tree, ch, 'baked_normal', 'ShaderNodeNormalMap', 'Baked Normal')
                    baked_normal.uv_map = self.uv_map

            # Check if image is available
            if baked.image:
                if baked.image.users == 1:
                    bpy.data.images.remove(baked.image)

            #Create new image
            img = bpy.data.images.new(name=tree.name + ' ' + ch.name, 
                    width=self.width, height=self.height) #, alpha=True, float_buffer=self.hdr)
            img.generated_type = 'BLANK'
            img.use_alpha = True
            if ch.type == 'NORMAL':
                img.generated_color = (0.5, 0.5, 1.0, 1.0)
            elif ch.type == 'VALUE':
                val = node.inputs[ch.io_index].default_value
                img.generated_color = (val, val, val, 1.0)
            elif ch.enable_alpha:
                img.generated_color = (0.0, 0.0, 0.0, 1.0)
            else:
                col = node.inputs[ch.io_index].default_value
                col = Color((col[0], col[1], col[2]))
                col = linear_to_srgb(col)
                img.generated_color = (col.r, col.g, col.b, 1.0)

            # Set image to tex node
            tex.image = img

            # Links to bake
            rgb = node.outputs[ch.io_index]
            if ch.colorspace == 'LINEAR' or ch.type == 'NORMAL':
                if ch.type == 'NORMAL':
                    rgb = create_link(mat.node_tree, rgb, norm.inputs[0])[0]
                rgb = create_link(mat.node_tree, rgb, linear.inputs[0])[0]
            mat.node_tree.links.new(rgb, emit.inputs[0])

            # Bake!
            bpy.ops.object.bake()

            # Bake alpha
            if ch.type == 'RGB' and ch.enable_alpha:
                # Create temp image
                alpha_img = bpy.data.images.new(name='__TEMP__', width=self.width, height=self.height) 

                # Bake setup
                create_link(mat.node_tree, node.outputs[ch.io_index+1], linear.inputs[0])
                create_link(mat.node_tree, linear.outputs[0], emit.inputs[0])
                tex.image = alpha_img

                # Bake
                bpy.ops.object.bake()

                # Copy alpha pixels to main image alpha channel
                img_pxs = list(img.pixels)
                alp_pxs = list(alpha_img.pixels)

                for y in range(self.height):
                    offset_y = self.width * 4 * y
                    for x in range(self.width):
                        a = alp_pxs[offset_y + (x*4)]
                        #a = srgb_to_linear_per_element(a)
                        img_pxs[offset_y + (x*4) + 3] = a

                img.pixels = img_pxs

                # Remove temp image
                bpy.data.images.remove(alpha_img)

            # Set image to baked node
            baked.image = img

        # Remove temp bake nodes
        simple_remove_node(mat.node_tree, tex)
        simple_remove_node(mat.node_tree, linear)
        simple_remove_node(mat.node_tree, emit)
        simple_remove_node(mat.node_tree, norm)

        # Recover original bsdf
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        # Recover bake settings
        recover_bake_settings(self, context)

        # Use bake results
        yp.use_baked = True

        # Rearrange
        rearrange_yp_nodes(tree)
        reconnect_yp_nodes(tree)

        return {'FINISHED'}

#class YDisableBakeResult(bpy.types.Operator):
#    """Disable Baked Image Result"""
#    bl_idname = "node.y_disable_baked_result"
#    bl_label = "Disable Bake Result"
#    bl_options = {'REGISTER', 'UNDO'}
#
#    @classmethod
#    def poll(cls, context):
#        node = get_active_ypaint_node()
#        return node and node.node_tree.yp.use_baked
#
#    def execute(self, context):
#        node = get_active_ypaint_node()
#        tree = node.node_tree
#        yp = tree.yp
#
#        yp.use_baked = False
#
#        reconnect_yp_nodes(tree)
#
#        return {'FINISHED'}

def update_use_baked(self, context):
    tree = self.id_data
    reconnect_yp_nodes(tree)

    # Trigger active image update
    if self.use_baked:
        self.active_channel_index = self.active_channel_index
    else:
        self.active_layer_index = self.active_layer_index

def register():
    bpy.utils.register_class(YBakeChannels)
    #bpy.utils.register_class(YDisableBakeResult)

def unregister():
    bpy.utils.unregister_class(YBakeChannels)
    #bpy.utils.unregister_class(YDisableBakeResult)
