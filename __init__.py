bl_info = {
    "name": "Ucup Multilayered Texture System",
    "author": "Yusuf Umar",
    "version": (0, 0, 0),
    "blender": (2, 79, 0),
    "location": "Node Editor > Properties > Texture Group",
    "description": "Texture Group Node can be substitute for layer manager within Cycles",
    "wiki_url": "http://twitter.com/ucupumar",
    "category": "Material",
}

if "bpy" in locals():
    import imp
    imp.reload(image_ops)
    imp.reload(tex_modifiers)
    imp.reload(common)
    imp.reload(node_arrangements)
    #print("Reloaded multifiles")
else:
    from . import image_ops, tex_modifiers
    #print("Imported multifiles")

import bpy, os, math
import tempfile
from bpy.props import *
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from .common import *
from .node_arrangements import *
from mathutils import *

# Imported node group names
#UDN = '~UDN Blend'
OVERLAY_VECTOR = '~Overlay Vector'
STRAIGHT_OVER = '~Straight Over Mix'

texture_type_items = (
        ('ShaderNodeTexImage', 'Image', ''),
        #('ShaderNodeTexEnvironment', 'Environment', ''),
        ('ShaderNodeTexBrick', 'Brick', ''),
        ('ShaderNodeTexChecker', 'Checker', ''),
        ('ShaderNodeTexGradient', 'Gradient', ''),
        ('ShaderNodeTexMagic', 'Magic', ''),
        ('ShaderNodeTexNoise', 'Noise', ''),
        #('ShaderNodeTexPointDensity', 'Point Density', ''),
        #('ShaderNodeTexSky', 'Sky', ''),
        ('ShaderNodeTexVoronoi', 'Voronoi', ''),
        ('ShaderNodeTexWave', 'Wave', ''),
        )

texcoord_type_items = (
        ('Generated', 'Generated', ''),
        ('Normal', 'Normal', ''),
        ('UV', 'UV', ''),
        ('Object', 'Object', ''),
        ('Camera', 'Camera', ''),
        ('Window', 'Window', ''),
        ('Reflection', 'Reflection', ''),
        )

vector_blend_items = (
        ('MIX', 'Mix', ''),
        #('UDN', 'UDN', ''),
        #('OVERLAY', 'Detail', '')
        ('OVERLAY', 'Overlay', '')
        )

normal_map_type_items = (
        ('BUMP', 'Bump Map', '', 'MATCAP_09', 0),
        ('NORMAL', 'Normal Map', '', 'MATCAP_23', 1)
        )

def add_io_from_new_channel(group_tree):
    # New channel should be the last item
    channel = group_tree.tg.channels[-1]

    if channel.type == 'RGB':
        socket_type = 'NodeSocketColor'
    elif channel.type == 'VALUE':
        socket_type = 'NodeSocketFloat'
    elif channel.type == 'VECTOR':
        socket_type = 'NodeSocketVector'

    inp = group_tree.inputs.new(socket_type, channel.name)
    out = group_tree.outputs.new(socket_type, channel.name)

    #group_tree.inputs.move(index,new_index)
    #group_tree.outputs.move(index,new_index)

    if channel.type == 'VALUE':
        inp.min_value = 0.0
        inp.max_value = 1.0
    elif channel.type == 'RGB':
        inp.default_value = (1,1,1,1)
    elif channel.type == 'VECTOR':
        inp.min_value = -1.0
        inp.max_value = 1.0
        inp.default_value = (0,0,1)

def set_input_default_value(group_node, channel):
    #channel = group_node.node_tree.tg.channels[index]
    
    # Set default value
    if channel.type == 'RGB':
        group_node.inputs[channel.io_index].default_value = (1,1,1,1)
        if channel.alpha:
            group_node.inputs[channel.io_index+1].default_value = 1.0
    if channel.type == 'VALUE':
        group_node.inputs[channel.io_index].default_value = 0.0
    if channel.type == 'VECTOR':
        group_node.inputs[channel.io_index].default_value = (0,0,1)

def update_image_editor_image(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if not area.spaces[0].use_image_pin:
                area.spaces[0].image = image

def check_create_node_link(tree, out, inp):
    if not any(l for l in out.links if l.to_socket == inp):
        tree.links.new(out, inp)

def refresh_layer_blends(group_tree):

    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links

    if tg.halt_update: return

    # Make blend type consistent with the nodes
    for tex in tg.textures:
        for i, ch in enumerate(tex.channels):
            group_ch = tg.channels[i]

            blend_frame = nodes.get(tex.blend_frame)
            blend = nodes.get(ch.blend)
            alpha_passthrough = nodes.get(ch.alpha_passthrough)

            intensity = nodes.get(ch.intensity)
            end_rgb = nodes.get(ch.end_rgb)

            if blend:
                if (
                    (ch.blend_type == 'MIX' and blend.bl_idname == 'ShaderNodeMixRGB') or
                    (ch.blend_type != 'MIX' and blend.bl_idname == 'ShaderNodeGroup') or
                    (ch.vector_blend == 'MIX' and blend.bl_idname == 'ShaderNodeGroup') or
                    (ch.vector_blend == 'OVERLAY' and blend.bl_idname == 'ShaderNodeMixRGB')
                    ):
                    nodes.remove(blend)
                    blend = None
                    ch.blend = ''
                    if alpha_passthrough: 
                        nodes.remove(alpha_passthrough)
                        alpha_passthrough = None
                        ch.alpha_passthrough = ''

            if not blend:
                if group_ch.type == 'RGB':

                    if ch.blend_type == 'MIX':
                        blend = nodes.new('ShaderNodeGroup')
                        blend.node_tree = bpy.data.node_groups.get(STRAIGHT_OVER)

                        # Links inside
                        links.new(end_rgb.outputs[0], blend.inputs[2])
                        links.new(intensity.outputs[0], blend.inputs[3])

                    else:
                        blend = nodes.new('ShaderNodeMixRGB')
                        blend.blend_type = ch.blend_type

                        alpha_passthrough = nodes.new('NodeReroute')
                        alpha_passthrough.label = 'Alpha Passthrough'
                        ch.alpha_passthrough = alpha_passthrough.name
                        if blend_frame: alpha_passthrough.parent = blend_frame

                        # Links inside
                        links.new(end_rgb.outputs[0], blend.inputs[2])
                        links.new(intensity.outputs[0], blend.inputs[0])

                elif group_ch.type == 'VECTOR':

                    bump = nodes.get(ch.bump)
                    normal = nodes.get(ch.normal)

                    if ch.vector_blend == 'OVERLAY':
                        blend = nodes.new('ShaderNodeGroup')
                        blend.node_tree = bpy.data.node_groups.get(OVERLAY_VECTOR)
                    else:
                        blend = nodes.new('ShaderNodeMixRGB')

                    # Links inside (also with refresh)
                    if ch.normal_map_type == 'BUMP':
                        links.new(normal.outputs[0], blend.inputs[2])
                        links.new(bump.outputs[0], blend.inputs[2])
                    else: 
                        links.new(bump.outputs[0], blend.inputs[2])
                        links.new(normal.outputs[0], blend.inputs[2])
                    links.new(intensity.outputs[0], blend.inputs[0])

                #elif group_ch.type == 'VALUE':
                else: # VALUE type
                    blend = nodes.new('ShaderNodeMixRGB')
                    blend.blend_type = ch.blend_type

                    # Links inside
                    links.new(end_rgb.outputs[0], blend.inputs[2])
                    links.new(intensity.outputs[0], blend.inputs[0])

                blend.label = 'Blend'
                if blend_frame: blend.parent = blend_frame
                ch.blend = blend.name
            
            mute = not tex.enable or not ch.enable
            if blend.mute != mute: blend.mute = mute

    # Link start and end if has no textures
    if len(tg.textures) == 0:
        for group_ch in tg.channels:
            start_entry = nodes.get(group_ch.start_entry)
            start_alpha_entry = nodes.get(group_ch.start_alpha_entry)
            end_entry = nodes.get(group_ch.end_entry)
            end_alpha_entry = nodes.get(group_ch.end_alpha_entry)

            check_create_node_link(group_tree, start_entry.outputs[0], end_entry.inputs[0])
            if start_alpha_entry and end_alpha_entry:
                check_create_node_link(group_tree, start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])

    # Link those blends
    for i, tex in enumerate(tg.textures):
        for j, ch in enumerate(tex.channels):
            group_ch = tg.channels[j]

            start_entry = nodes.get(group_ch.start_entry)
            start_alpha_entry = nodes.get(group_ch.start_alpha_entry)
            end_entry = nodes.get(group_ch.end_entry)
            end_alpha_entry = nodes.get(group_ch.end_alpha_entry)

            blend = nodes.get(ch.blend)
            alpha_passthrough = nodes.get(ch.alpha_passthrough)

            # Check vector blend changes
            if group_ch.type == 'VECTOR':

                bump = nodes.get(ch.bump)
                normal = nodes.get(ch.normal)

                if ch.normal_map_type == 'BUMP':
                    #check_create_node_link(group_tree, normal.outputs[0], blend.inputs[2])
                    check_create_node_link(group_tree, bump.outputs[0], blend.inputs[2])
                else:
                    #check_create_node_link(group_tree, bump.outputs[0], blend.inputs[2])
                    check_create_node_link(group_tree, normal.outputs[0], blend.inputs[2])

            # Check blend type changes
            elif blend.bl_idname == 'ShaderNodeMixRGB':
                if blend.blend_type != ch.blend_type: blend.blend_type = ch.blend_type

            # Last texture
            if i == 0: 

                check_create_node_link(group_tree, blend.outputs[0], end_entry.inputs[0])
                if group_ch.type == 'RGB' and ch.blend_type == 'MIX':
                    check_create_node_link(group_tree, blend.outputs[1], end_alpha_entry.inputs[0])
                if alpha_passthrough:
                    check_create_node_link(group_tree, alpha_passthrough.outputs[0], end_alpha_entry.inputs[0])

            # First texture
            if i == len(tg.textures)-1: 

                if group_ch.type == 'RGB' and ch.blend_type == 'MIX':
                    check_create_node_link(group_tree, start_entry.outputs[0], blend.inputs[0])
                    check_create_node_link(group_tree, start_alpha_entry.outputs[0], blend.inputs[1])
                else:
                    check_create_node_link(group_tree, start_entry.outputs[0], blend.inputs[1])

                if alpha_passthrough:
                    check_create_node_link(group_tree, start_alpha_entry.outputs[0], alpha_passthrough.inputs[0])

            # Mid textures
            if i != 0:
                next_ch = tg.textures[i-1].channels[j]
                next_blend = nodes.get(next_ch.blend)
                next_alpha_passthrough = nodes.get(next_ch.alpha_passthrough)

                if group_ch.type == 'RGB':
                    if ch.blend_type == 'MIX' and next_ch.blend_type == 'MIX':
                        check_create_node_link(group_tree, blend.outputs[0], next_blend.inputs[0])
                        check_create_node_link(group_tree, blend.outputs[1], next_blend.inputs[1])
                    elif ch.blend_type == 'MIX' and next_ch.blend_type != 'MIX':
                        check_create_node_link(group_tree, blend.outputs[0], next_blend.inputs[1])
                        check_create_node_link(group_tree, blend.outputs[1], next_alpha_passthrough.inputs[0])
                    elif ch.blend_type != 'MIX' and next_ch.blend_type == 'MIX':
                        check_create_node_link(group_tree, blend.outputs[0], next_blend.inputs[0])
                        check_create_node_link(group_tree, alpha_passthrough.outputs[0], next_blend.inputs[1])
                    else:
                        check_create_node_link(group_tree, blend.outputs[0], next_blend.inputs[1])
                        check_create_node_link(group_tree, alpha_passthrough.outputs[0], next_alpha_passthrough.inputs[0])
                else:
                    check_create_node_link(group_tree, blend.outputs[0], next_blend.inputs[1])

    rearrange_nodes(group_tree)

def create_texture_channel_nodes(group_tree, texture, channel):

    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links

    ch_index = [i for i, c in enumerate(texture.channels) if c == channel][0]
    group_ch = tg.channels[ch_index]

    # Linear nodes
    #linear = nodes.new('ShaderNodeGamma')
    #linear.label = 'Source Linear'
    #linear.inputs[1].default_value = 1.0/GAMMA
    #channel.linear = linear.name

    # Modifier pipeline nodes
    start_rgb = nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    channel.start_rgb = start_rgb.name

    start_alpha = nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    channel.start_alpha = start_alpha.name

    end_rgb = nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    channel.end_rgb = end_rgb.name

    end_alpha = nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    channel.end_alpha = end_alpha.name

    # Intensity nodes
    intensity = nodes.new('ShaderNodeMixRGB')
    #intensity.blend_type = 'MULTIPLY'
    intensity.label = 'Intensity'
    intensity.inputs[0].default_value = 1.0
    intensity.inputs[1].default_value = (0,0,0,1)
    intensity.inputs[2].default_value = (1,1,1,1)
    channel.intensity = intensity.name

    # Blend frame
    blend_frame = nodes.get(texture.blend_frame)
    if not blend_frame:
        blend_frame = nodes.new('NodeFrame')
        blend_frame.label = 'Blend'
        texture.blend_frame = blend_frame.name

    # Temporary blend, possibly replaced later
    #blend = nodes.new('ShaderNodeMixRGB')
    #blend.label = 'Blend'
    #blend.parent = blend_frame
    #channel.blend = blend.name

    #if group_ch.type == 'RGB':
    #    alpha_passthrough = nodes.new('NodeReroute')
    #    alpha_passthrough.label = 'Alpha Passthrough'
    #    channel.alpha_passthrough = alpha_passthrough.name
    #    alpha_passthrough.parent = blend_frame

    # Normal nodes
    if group_ch.type == 'VECTOR':
        normal = nodes.new('ShaderNodeNormalMap')
        channel.normal = normal.name

        bump_base = nodes.new('ShaderNodeMixRGB')
        bump_base.label = 'Bump Base'
        #mid_value = math.pow(0.5, 1/GAMMA)
        #bump_base.inputs[1].default_value = (mid_value, mid_value, mid_value, 1.0)
        bump_base.inputs[1].default_value = (0.5, 0.5, 0.5, 1.0)
        channel.bump_base = bump_base.name

        bump = nodes.new('ShaderNodeBump')
        bump.inputs[1].default_value = 0.05
        channel.bump = bump.name

    #intensity.parent = blend_frame

    # Get source RGB and alpha
    #linear = nodes.get(texture.linear)
    solid_alpha = nodes.get(texture.solid_alpha)
    source = nodes.get(texture.source)

    # Modifier frame
    modifier_frame = nodes.get(channel.modifier_frame)
    if not modifier_frame:
        modifier_frame = nodes.new('NodeFrame')
        modifier_frame.label = 'Modifiers'
        channel.modifier_frame = modifier_frame.name

    #intensity.parent = modifier_frame
    start_rgb.parent = modifier_frame
    start_alpha.parent = modifier_frame
    end_rgb.parent = modifier_frame
    end_alpha.parent = modifier_frame

    # Link nodes
    links.new(source.outputs[0], start_rgb.inputs[0])
    #links.new(source.outputs[0], linear.inputs[0])
    #links.new(linear.outputs[0], start_rgb.inputs[0])
    if solid_alpha:
        links.new(solid_alpha.outputs[0], start_alpha.inputs[0])
    else: links.new(source.outputs[1], start_alpha.inputs[0])

    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])
    #links.new(start_alpha.outputs[0], intensity.inputs[2])

    if group_ch.type == 'VECTOR':
        links.new(end_alpha.outputs[0], bump_base.inputs[0])
        links.new(end_rgb.outputs[0], bump_base.inputs[2])
        links.new(bump_base.outputs[0], bump.inputs[2])
        links.new(end_rgb.outputs[0], normal.inputs[1])

        # Bump as default
        #links.new(bump.outputs[0], blend.inputs[2])
    #else:
    #    links.new(end_rgb.outputs[0], blend.inputs[2])

    links.new(end_alpha.outputs[0], intensity.inputs[2])
    #links.new(intensity.outputs[0], blend.inputs[0])

    #return blend

def create_group_channel_nodes(group_tree, channel):
    # TEMPORARY SOLUTION
    # New channel should be the last item
    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links
    #last_index = len(tg.channels)-1
    #channel = tg.channels[last_index]

    # Get start and end node
    start_node = nodes.get(tg.start)
    end_node = nodes.get(tg.end)

    start_linear = None
    start_convert = None

    end_linear = None
    end_convert = None

    # Get start and end frame
    start_frame = nodes.get(tg.start_frame)
    if not start_frame:
        start_frame = nodes.new('NodeFrame')
        start_frame.label = 'Start'
        tg.start_frame = start_frame.name

    end_entry_frame = nodes.get(tg.end_entry_frame)
    if not end_entry_frame:
        end_entry_frame = nodes.new('NodeFrame')
        end_entry_frame.label = 'End'
        tg.end_entry_frame = end_entry_frame.name

    #modifier_frame = nodes.get(channel.modifier_frame)
    modifier_frame = nodes.new('NodeFrame')
    modifier_frame.label = 'Modifier'
    channel.modifier_frame = modifier_frame.name

    end_linear_frame = nodes.get(tg.end_linear_frame)
    if not end_linear_frame:
        end_linear_frame = nodes.new('NodeFrame')
        end_linear_frame.label = 'End Linear'
        tg.end_linear_frame = end_linear_frame.name

    # Create linarize node and converter node
    if channel.type in {'RGB', 'VALUE'}:
        if channel.type == 'RGB':
            start_linear = nodes.new('ShaderNodeGamma')
        else: 
            start_linear = nodes.new('ShaderNodeMath')
            start_linear.operation = 'POWER'
        start_linear.label = 'Start Linear'
        start_linear.inputs[1].default_value = 1.0/GAMMA

        start_linear.parent = start_frame
        channel.start_linear = start_linear.name

        if channel.type == 'RGB':
            end_linear = nodes.new('ShaderNodeGamma')
        else: 
            end_linear = nodes.new('ShaderNodeMath')
            end_linear.operation = 'POWER'
        end_linear.label = 'End Linear'
        end_linear.inputs[1].default_value = GAMMA

        end_linear.parent = end_linear_frame
        channel.end_linear = end_linear.name

    start_entry = nodes.new('NodeReroute')
    start_entry.label = 'Start Entry'
    start_entry.parent = start_frame
    channel.start_entry = start_entry.name

    end_entry = nodes.new('NodeReroute')
    end_entry.label = 'End Entry'
    end_entry.parent = end_entry_frame
    channel.end_entry = end_entry.name

    if channel.type == 'RGB':
        start_alpha_entry = nodes.new('NodeReroute')
        start_alpha_entry.label = 'Start Alpha Entry'
        start_alpha_entry.parent = start_frame
        channel.start_alpha_entry = start_alpha_entry.name

        solid_alpha = nodes.new('ShaderNodeValue')
        solid_alpha.outputs[0].default_value = 1.0
        solid_alpha.label = 'Solid Alpha'
        solid_alpha.parent = start_frame
        channel.solid_alpha = solid_alpha.name

        end_alpha_entry = nodes.new('NodeReroute')
        end_alpha_entry.label = 'End Alpha Entry'
        end_alpha_entry.parent = end_entry_frame
        channel.end_alpha_entry = end_alpha_entry.name

    # Modifier pipeline
    start_rgb = nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    start_rgb.parent = modifier_frame
    channel.start_rgb = start_rgb.name

    start_alpha = nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    start_alpha.parent = modifier_frame
    channel.start_alpha = start_alpha.name

    end_rgb = nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    end_rgb.parent = modifier_frame
    channel.end_rgb = end_rgb.name

    end_alpha = nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    end_alpha.parent = modifier_frame
    channel.end_alpha = end_alpha.name

    # Link nodes
    if start_linear:
        links.new(start_node.outputs[channel.io_index], start_linear.inputs[0])
        links.new(start_linear.outputs[0], start_entry.inputs[0])
    else:
        links.new(start_node.outputs[channel.io_index], start_entry.inputs[0])

    links.new(end_entry.outputs[0], start_rgb.inputs[0])
    links.new(start_rgb.outputs[0], end_rgb.inputs[0])
    links.new(start_alpha.outputs[0], end_alpha.inputs[0])
    if channel.type == 'RGB':
        links.new(solid_alpha.outputs[0], start_alpha_entry.inputs[0])
        links.new(end_alpha_entry.outputs[0], start_alpha.inputs[0])

    if end_linear:
        links.new(end_rgb.outputs[0], end_linear.inputs[0])
        links.new(end_linear.outputs[0], end_node.inputs[channel.io_index])
    else:
        links.new(end_rgb.outputs[0], end_node.inputs[channel.io_index])

    # Link between textures
    if len(tg.textures) == 0:
        links.new(start_entry.outputs[0], end_entry.inputs[0])
        if channel.type == 'RGB':
            links.new(start_alpha_entry.outputs[0], end_alpha_entry.inputs[0])
    else:
        for i, t in reversed(list(enumerate(tg.textures))):

            # Add new channel
            c = t.channels.add()

            # Add new nodes
            create_texture_channel_nodes(group_tree, t, c)

def create_new_group_tree(mat):

    # Group name is based from the material
    group_name = 'TexGroup ' + mat.name

    # Create new group tree
    group_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    group_tree.tg.is_tg_node = True

    # Add new channel
    channel = group_tree.tg.channels.add()
    channel.name = 'Color'
    #group_tree.tg.temp_channels.add() # Also add temp channel

    add_io_from_new_channel(group_tree)
    channel.io_index = 0

    # Create start and end node
    start_node = group_tree.nodes.new('NodeGroupInput')
    end_node = group_tree.nodes.new('NodeGroupOutput')
    group_tree.tg.start = start_node.name
    group_tree.tg.end = end_node.name

    # Link start and end node then rearrange the nodes
    create_group_channel_nodes(group_tree, channel)

    return group_tree

class YNewTextureGroupNode(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_node"
    bl_label = "Add new Texture Group Node"
    bl_description = "Add new texture group node"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def store_mouse_cursor(context, event):
        space = context.space_data
        tree = space.edit_tree

        # convert mouse position to the View2D for later node placement
        if context.region.type == 'WINDOW':
            # convert mouse position to the View2D for later node placement
            space.cursor_location_from_region(
                    event.mouse_region_x, event.mouse_region_y)
        else:
            space.cursor_location = tree.view_center

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree to add nodes to
        return ((space.type == 'NODE_EDITOR') and
                space.edit_tree and not space.edit_tree.library)

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        mat = space.id

        # select only the new node
        for n in tree.nodes:
            n.select = False

        # Create new group tree
        group_tree = create_new_group_tree(mat)

        # Create new group node
        node = tree.nodes.new(type='ShaderNodeGroup')
        node.node_tree = group_tree

        # Set default input value
        set_input_default_value(node, group_tree.tg.channels[0])

        # Rearrange nodes
        rearrange_nodes(group_tree)

        # Set the location of new node
        node.select = True
        tree.nodes.active = node
        node.location = space.cursor_location

        return {'FINISHED'}

    # Default invoke stores the mouse position to place the node correctly
    # and optionally invokes the transform operator
    def invoke(self, context, event):
        self.store_mouse_cursor(context, event)
        result = self.execute(context)

        if 'FINISHED' in result:
            # Removes the node again if transform is canceled
            bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')

        return result

class YNewTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_add_new_texture_group_channel"
    bl_label = "Add new Texture Group Channel"
    bl_description = "Add new texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo')

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def invoke(self, context, event):
        group_node = get_active_texture_group_node()
        channels = group_node.node_tree.tg.channels

        if self.type == 'RGB':
            self.name = 'Color'
        elif self.type == 'VALUE':
            self.name = 'Value'
        elif self.type == 'VECTOR':
            self.name = 'Normal'

        # Check if name already available on the list
        self.name = get_unique_name(self.name, channels)

        return context.window_manager.invoke_props_dialog(self)
        #return context.window_manager.invoke_popup(self)

    def check(self, context):
        return True

    def draw(self, context):
        self.layout.prop(self, 'name', text='Name')

    def execute(self, context):
        #node = context.active_node
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tg = group_tree.tg
        channels = tg.channels

        # Check if channel with same name is already available
        same_channel = [c for c in channels if c.name == self.name]
        if same_channel:
            self.report({'ERROR'}, "Channel named '" + self.name +"' is already available!")
            return {'CANCELLED'}

        # Add new channel
        channel = channels.add()
        channel.type = self.type
        #temp_ch = group_tree.tg.temp_channels.add()
        #temp_ch.enable = False

        # Add input and output to the tree
        add_io_from_new_channel(group_tree)

        # Get last index
        last_index = len(channels)-1

        # Get IO index
        io_index = last_index
        for ch in tg.channels:
            if ch.type == 'RGB' and ch.alpha:
                io_index += 1

        channel.io_index = io_index
        channel.name = self.name

        # Link new channel
        create_group_channel_nodes(group_tree, channel)

        # New channel is disabled in texture by default
        for tex in tg.textures:
            tex.channels[last_index].enable = False

        # Refresh texture channel blend nodes
        refresh_layer_blends(group_tree)

        # Rearrange nodes
        #rearrange_nodes(group_tree)

        # Set input default value
        set_input_default_value(node, channel)

        # Change active channel
        group_tree.tg.active_channel_index = last_index

        return {'FINISHED'}

class YMoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_move_texture_group_channel"
    bl_label = "Move Texture Group Channel"
    bl_description = "Move texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree
        tg = group_tree.tg
        inputs = group_tree.inputs
        outputs = group_tree.outputs

        # Get active channel
        index = tg.active_channel_index
        channel = tg.channels[index]
        num_chs = len(tg.channels)

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_chs-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Get IO index
        swap_ch = tg.channels[new_index]
        io_index = channel.io_index
        io_index_swap = swap_ch.io_index

        # Move IO
        if channel.type == 'RGB' and channel.alpha:
            if swap_ch.type == 'RGB' and swap_ch.alpha:
                if io_index > io_index_swap:
                    inputs.move(io_index, io_index_swap)
                    inputs.move(io_index+1, io_index_swap+1)
                    outputs.move(io_index, io_index_swap)
                    outputs.move(io_index+1, io_index_swap+1)
                else:
                    inputs.move(io_index, io_index_swap)
                    inputs.move(io_index, io_index_swap+1)
                    outputs.move(io_index, io_index_swap)
                    outputs.move(io_index, io_index_swap+1)
            else:
                if io_index > io_index_swap:
                    inputs.move(io_index, io_index_swap)
                    inputs.move(io_index+1, io_index_swap+1)
                    outputs.move(io_index, io_index_swap)
                    outputs.move(io_index+1, io_index_swap+1)
                else:
                    inputs.move(io_index+1, io_index_swap)
                    inputs.move(io_index, io_index_swap-1)
                    outputs.move(io_index+1, io_index_swap)
                    outputs.move(io_index, io_index_swap-1)
        else:
            if swap_ch.type == 'RGB' and swap_ch.alpha:
                if io_index > io_index_swap:
                    inputs.move(io_index, io_index_swap)
                    outputs.move(io_index, io_index_swap)
                else:
                    inputs.move(io_index, io_index_swap+1)
                    outputs.move(io_index, io_index_swap+1)
            else:
                inputs.move(io_index, io_index_swap)
                outputs.move(io_index, io_index_swap)

        # Move channel
        tg.channels.move(index, new_index)
        #tg.temp_channels.move(index, new_index) # Temp channels

        # Move channel inside textures
        for tex in tg.textures:
            tex.channels.move(index, new_index)

        # Reindex IO
        i = 0
        for ch in tg.channels:
            ch.io_index = i
            i += 1
            if ch.type == 'RGB' and ch.alpha: i += 1

        # Rearrange nodes
        rearrange_nodes(group_tree)

        # Set active index
        tg.active_channel_index = new_index

        return {'FINISHED'}

class YRemoveTextureGroupChannel(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_group_channel"
    bl_label = "Remove Texture Group Channel"
    bl_description = "Remove texture group channel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.channels) > 0

    def execute(self, context):
        group_node = get_active_texture_group_node()
        group_tree = group_node.node_tree
        tg = group_tree.tg
        nodes = group_tree.nodes
        inputs = group_tree.inputs
        outputs = group_tree.outputs

        # Get active channel
        channel_idx = tg.active_channel_index
        channel = tg.channels[channel_idx]
        channel_name = channel.name

        # Remove channel nodes from textures
        for t in tg.textures:
            ch = t.channels[channel_idx]

            nodes.remove(nodes.get(ch.blend))
            nodes.remove(nodes.get(ch.start_rgb))
            nodes.remove(nodes.get(ch.start_alpha))
            nodes.remove(nodes.get(ch.end_rgb))
            nodes.remove(nodes.get(ch.end_alpha))
            nodes.remove(nodes.get(ch.modifier_frame))
            nodes.remove(nodes.get(ch.intensity))
            #nodes.remove(nodes.get(ch.linear))
            try: nodes.remove(nodes.get(ch.alpha_passthrough))
            except: pass
            try: nodes.remove(nodes.get(ch.normal))
            except: pass
            try: nodes.remove(nodes.get(ch.bump))
            except: pass
            try: nodes.remove(nodes.get(ch.bump_base))
            except: pass

            # Remove modifiers
            for mod in ch.modifiers:
                tex_modifiers.delete_modifier_nodes(nodes, mod)

            t.channels.remove(channel_idx)

        # Remove start and end nodes
        nodes.remove(nodes.get(channel.start_entry))
        nodes.remove(nodes.get(channel.end_entry))
        try: nodes.remove(nodes.get(channel.start_linear)) 
        except: pass
        try: nodes.remove(nodes.get(channel.end_linear)) 
        except: pass
        try: nodes.remove(nodes.get(channel.start_alpha_entry)) 
        except: pass
        try: nodes.remove(nodes.get(channel.solid_alpha)) 
        except: pass
        try: nodes.remove(nodes.get(channel.end_alpha_entry)) 
        except: pass

        # Remove channel modifiers
        nodes.remove(nodes.get(channel.start_rgb))
        nodes.remove(nodes.get(channel.start_alpha))
        nodes.remove(nodes.get(channel.end_rgb))
        nodes.remove(nodes.get(channel.end_alpha))
        nodes.remove(nodes.get(channel.modifier_frame))

        for mod in channel.modifiers:
            tex_modifiers.delete_modifier_nodes(nodes, mod)

        # Remove some frames if it's the last channel
        if len(tg.channels) == 1:
            nodes.remove(nodes.get(tg.start_frame))
            nodes.remove(nodes.get(tg.end_entry_frame))
            nodes.remove(nodes.get(tg.end_linear_frame))
            tg.start_frame = ''
            tg.end_entry_frame = ''
            tg.end_linear_frame = ''
            for t in tg.textures:
                nodes.remove(nodes.get(t.blend_frame))
                t.blend_frame = ''

        # Remove channel from tree
        inputs.remove(inputs[channel.io_index])
        outputs.remove(outputs[channel.io_index])

        shift = 1

        if channel.type == 'RGB' and channel.alpha:
            inputs.remove(inputs[channel.io_index])
            outputs.remove(outputs[channel.io_index])

            shift = 2

        # Shift IO index
        for ch in tg.channels:
            if ch.io_index > channel.io_index:
                ch.io_index -= shift

        # Remove channel
        tg.channels.remove(channel_idx)
        #tg.temp_channels.remove(channel_idx)

        # Rearrange nodes
        rearrange_nodes(group_tree)

        # Set new active index
        if (tg.active_channel_index == len(tg.channels) and
            tg.active_channel_index > 0
            ): tg.active_channel_index -= 1

        return {'FINISHED'}

def channel_items(self, context):
    node = get_active_texture_group_node()
    tg = node.node_tree.tg

    items = []

    for i, ch in enumerate(tg.channels):
        items.append((str(i), ch.name, '', 'LINK', i))

    items.append(('-1', 'All Channels', '', 'LINK', len(items)))

    return items

def add_new_texture(tex_name, tex_type, channel_idx, blend_type, vector_blend, normal_map_type, 
        texcoord_type, uv_map_name='', add_rgb_to_intensity=False, image=None):

    group_node = get_active_texture_group_node()
    group_tree = group_node.node_tree
    nodes = group_tree.nodes
    links = group_tree.links
    tg = group_tree.tg

    # Add texture to group
    tex = tg.textures.add()
    tex.type = tex_type
    tex.name = tex_name

    # Move new texture to current index
    last_index = len(tg.textures)-1
    index = tg.active_texture_index
    tg.textures.move(last_index, index)
    tex = tg.textures[index] # Repoint to new index

    # Add source frame
    source_frame = nodes.new('NodeFrame')
    source_frame.label = 'Source'
    tex.source_frame = source_frame.name

    # Add source node
    source = nodes.new(tex_type)
    source.label = 'Source'
    source.parent = source_frame
    tex.source = source.name

    # Always set non color to image node because of linear pipeline
    if tex_type == 'ShaderNodeTexImage':
        source.color_space = 'NONE'

    # Add texcoord node
    texcoord = nodes.new('ShaderNodeTexCoord')
    texcoord.label = 'Source TexCoord'
    texcoord.parent = source_frame
    tex.texcoord = texcoord.name

    # Add uv map node
    uv_map = nodes.new('ShaderNodeUVMap')
    uv_map.label = 'Source UV Map'
    uv_map.parent = source_frame
    uv_map.uv_map = uv_map_name
    tex.uv_map = uv_map.name

    # Set tex coordinate type
    tex.texcoord_type = texcoord_type

    # Add new image if it's image texture
    if tex_type == 'ShaderNodeTexImage':
        source.image = image

    # Solid alpha for non image texture
    if tex_type != 'ShaderNodeTexImage':
        solid_alpha = nodes.new('ShaderNodeValue')
        solid_alpha.label = 'Solid Alpha'
        solid_alpha.outputs[0].default_value = 1.0
        tex.solid_alpha = solid_alpha.name

        solid_alpha.parent = source_frame

    # Add channels
    shortcut_created = False
    for i, ch in enumerate(tg.channels):
        # Add new channel to current texture
        c = tex.channels.add()

        # Add blend and other nodes
        create_texture_channel_nodes(group_tree, tex, c)

        # Set some props to selected channel
        if channel_idx == i or channel_idx == -1:
            c.enable = True
            if ch.type == 'VECTOR':
                c.vector_blend = vector_blend
                c.normal_map_type = normal_map_type
            else:
                c.blend_type = blend_type
        else: 
            c.enable = False

        # If RGB to intensity is selected, bump base is better be 0.0
        if add_rgb_to_intensity:
            if ch.type == 'VECTOR':
                c.bump_base_value = 0.0

            m = tex_modifiers.add_new_modifier(group_tree, c, 'RGB_TO_INTENSITY')

            if c.enable and ch.type == 'RGB' and not shortcut_created:
                m.shortcut = True
                shortcut_created = True

    # Refresh paint image by updating the index
    tg.active_texture_index = index

    #return tex

class YNewTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_new_texture_layer"
    bl_label = "New Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    # For image texture
    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)
    color = FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    alpha = BoolProperty(name='Alpha', default=True)
    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items)

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = blend_type_items,
        default = 'MIX')

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    uv_map = StringProperty(default='')

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'BUMP')

    #temp_channels = CollectionProperty(type=YTempChannel)

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()
        #return hasattr(context, 'group_node') and context.group_node

    def invoke(self, context, event):
        #self.group_node = node = context.group_node
        #print(self.group_node)
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        #tg = context.group_node.node_tree.tg
        obj = context.object

        if self.type != 'ShaderNodeTexImage':
            name = self.type.replace('ShaderNodeTex', '')
            items = tg.textures
        else:
            name = obj.active_material.name
            items = bpy.data.images

        self.name = get_unique_name(name, items)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_textures) > 0:
            self.uv_map = obj.data.uv_textures.active.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        #tg = self.group_node.node_tree.tg
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        obj = context.object

        #col = self.layout.column(align=True)

        if len(tg.channels) == 0:
            self.layout.label('No channel found! Still want to create a texture?', icon='ERROR')
            return

        channel = tg.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        #row = self.layout.row(align=True)
        row = self.layout.split(percentage=0.4)
        col = row.column(align=False)

        #col.label('Type: ' + type_name)
        col.label('Name:')
        if self.type == 'ShaderNodeTexImage':
            col.label('Width:')
            col.label('Height:')
            col.label('Color:')
            col.label('')
            #col.label('Generated Type')
            col.label('')
            #col.label('Blend:')
            #col.label('UV Layer')

        col.label('Vector:')
        col.label('Channel:')
        if channel and channel.type == 'VECTOR':
            col.label('Type:')
        #for i, ch in enumerate(tg.channels):
        #    rrow = col.row(align=True)
        #    rrow.label(ch.name + ':', icon='LINK')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'ShaderNodeTexImage':
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')
            col.prop(self, 'color', text='')
            col.prop(self, 'alpha')
            #col.prop(self, 'generated_type', text='')
            col.prop(self, 'hdr')
            #col.prop(self, 'blend_type', text='')

        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        #col.label('')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'VECTOR':
                rrow.prop(self, 'vector_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        #for i, ch in enumerate(tg.channels):
        #    rrow = col.row(align=True)
        #    rrow.active = tg.temp_channels[i].enable
        #    rrow.prop(tg.temp_channels[i], 'enable', text='')
        #    if ch.type == 'VECTOR':
        #        rrow.prop(tg.temp_channels[i], 'vector_blend', text='')
        #    else:
        #        rrow.prop(tg.temp_channels[i], 'blend_type', text='')
        #    if ch.type == 'RGB':
        #        icon = 'RESTRICT_COLOR_ON' if tg.temp_channels[i].add_rgb_to_intensity else 'RESTRICT_COLOR_OFF'
        #        rrow.prop(tg.temp_channels[i], 'add_rgb_to_intensity', text='', icon=icon, emboss=False)
        #        #rrow.prop(tg.temp_channels[i], 'add_rgb_to_intensity', text='') #, icon='COLOR')
        #        #rrow.label('RGB2i')
        #    else:
        #        rrow.label('', icon='RESTRICT_COLOR_OFF')

    def execute(self, context):

        node = get_active_texture_group_node()
        tg = node.node_tree.tg

        # Check if texture with same name is already available
        same_name = [t for t in tg.textures if t.name == self.name]
        if same_name:
            self.report({'ERROR'}, "Texture named '" + tex_name +"' is already available!")
            return {'CANCELLED'}

        img = None
        if self.type == 'ShaderNodeTexImage':
            img = bpy.data.images.new(self.name, self.width, self.height, self.alpha, self.hdr)
            #img.generated_type = self.generated_type
            img.generated_type = 'BLANK'
            img.generated_color = self.color
            update_image_editor_image(context, img)

        tg.halt_update = True
        add_new_texture(self.name, self.type, int(self.channel_idx), self.blend_type, self.vector_blend, 
                self.normal_map_type, self.texcoord_type, self.uv_map, self.add_rgb_to_intensity, img)
        tg.halt_update = False

        # Refresh texture channel blend nodes
        refresh_layer_blends(node.node_tree)

        # Rearrange nodes
        #rearrange_nodes(node.node_tree)

        return {'FINISHED'}

class YOpenImageToLayer(bpy.types.Operator, ImportHelper):
    """Open Image to Texture Layer"""
    bl_idname = "node.y_open_image_to_layer"
    bl_label = "Open Image to Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files = CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory = StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type = EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative = BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'OVERLAY')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'NORMAL')

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_group_node()

    def invoke(self, context, event):
        obj = context.object

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_textures) > 0:
            self.uv_map = obj.data.uv_textures.active.name

        #return context.window_manager.invoke_props_dialog(self)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        obj = context.object

        channel = tg.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        
        row = self.layout.row()

        col = row.column()
        col.label('Vector:')
        col.label('Channel:')
        if channel and channel.type == 'VECTOR':
            col.label('Type:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        #col.label('')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'VECTOR':
                rrow.prop(self, 'vector_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        self.layout.prop(self, 'relative')

    def execute(self, context):
        node = get_active_texture_group_node()

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        node.node_tree.tg.halt_update = True

        for image in images:
            if self.relative:
                image.filepath = bpy.path.relpath(image.filepath)

            add_new_texture(image.name, 'ShaderNodeTexImage', int(self.channel_idx), self.blend_type, 
                    self.vector_blend, self.normal_map_type, self.texcoord_type, self.uv_map,
                    self.add_rgb_to_intensity, image)

        node.node_tree.tg.halt_update = False

        # Refresh texture channel blend nodes
        refresh_layer_blends(node.node_tree)

        # Rearrange nodes
        #rearrange_nodes(node.node_tree)

        return {'FINISHED'}

class YOpenAvailableImageToLayer(bpy.types.Operator):
    """Open Available Image to Texture Layer"""
    bl_idname = "node.y_open_available_image_to_layer"
    bl_label = "Open Available Image to Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'BUMP')

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_group_node()

    def invoke(self, context, event):
        obj = context.object

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_textures) > 0:
            self.uv_map = obj.data.uv_textures.active.name

        # Update image names
        self.image_coll.clear()
        imgs = bpy.data.images
        for img in imgs:
            self.image_coll.add().name = img.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        node = get_active_texture_group_node()
        tg = node.node_tree.tg
        obj = context.object

        channel = tg.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        
        row = self.layout.row()

        col = row.column()
        col.label('Vector:')
        col.label('Channel:')
        if channel and channel.type == 'VECTOR':
            col.label('Type:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        #col.label('')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'VECTOR':
                rrow.prop(self, 'vector_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

    def execute(self, context):
        node = get_active_texture_group_node()

        if self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}

        node.node_tree.tg.halt_update = True

        image = bpy.data.images.get(self.image_name)
        add_new_texture(image.name, 'ShaderNodeTexImage', int(self.channel_idx), self.blend_type, 
                self.vector_blend, self.normal_map_type, self.texcoord_type, self.uv_map, 
                self.add_rgb_to_intensity, image)

        node.node_tree.tg.halt_update = False

        # Refresh texture channel blend nodes
        refresh_layer_blends(node.node_tree)

        # Rearrange nodes
        #rearrange_nodes(node.node_tree)

        return {'FINISHED'}

class YMoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_move_texture_layer"
    bl_label = "Move Texture Layer"
    bl_description = "Move texture layer"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.textures) > 0

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tg = group_tree.tg

        num_tex = len(tg.textures)
        tex_idx = tg.active_texture_index
        tex = tg.textures[tex_idx]
        
        # Move image slot
        if self.direction == 'UP' and tex_idx > 0:
            swap_idx = tex_idx-1
        elif self.direction == 'DOWN' and tex_idx < num_tex-1:
            swap_idx = tex_idx+1
        else:
            return {'CANCELLED'}

        swap_tex = tg.textures[swap_idx]

        for i, ch in enumerate(tex.channels):
            blend = nodes.get(ch.blend)
            swap_blend = nodes.get(swap_tex.channels[i].blend)

            inp_blend = blend.inputs[1].links[0].from_socket
            out_blend = blend.outputs[0].links[0].to_socket

            swap_in_blend = swap_blend.inputs[1].links[0].from_socket
            swap_out_blend = swap_blend.outputs[0].links[0].to_socket

            if self.direction == 'UP':
                group_tree.links.new(blend.outputs[0], swap_out_blend)
                group_tree.links.new(swap_blend.outputs[0], blend.inputs[1])
                group_tree.links.new(inp_blend, swap_blend.inputs[1])
            else:
                group_tree.links.new(swap_blend.outputs[0], out_blend)
                group_tree.links.new(blend.outputs[0], swap_blend.inputs[1])
                group_tree.links.new(swap_in_blend, blend.inputs[1])

        # Swap texture
        tg.textures.move(tex_idx, swap_idx)
        tg.active_texture_index = swap_idx

        # Refresh texture channel blend nodes
        refresh_layer_blends(group_tree)

        # Rearrange nodes
        #rearrange_nodes(group_tree)

        return {'FINISHED'}

class YRemoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_layer"
    bl_label = "Remove Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_group_node()
        return group_node and len(group_node.node_tree.tg.textures) > 0

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tg = group_tree.tg

        tex = tg.textures[tg.active_texture_index]

        # Delete source
        nodes.remove(nodes.get(tex.source))
        nodes.remove(nodes.get(tex.texcoord))
        nodes.remove(nodes.get(tex.uv_map))
        try: nodes.remove(nodes.get(tex.solid_alpha))
        except: pass

        nodes.remove(nodes.get(tex.source_frame))
        try: nodes.remove(nodes.get(tex.blend_frame))
        except: pass

        # Delete channels
        for ch in tex.channels:
            # Delete blend node and dealing with the links
            blend = nodes.get(ch.blend)
            #inp = blend.inputs[1].links[0].from_socket
            #outp = blend.outputs[0].links[0].to_socket
            #group_tree.links.new(inp, outp)
            nodes.remove(blend)

            nodes.remove(nodes.get(ch.intensity))
            #nodes.remove(nodes.get(ch.linear))

            nodes.remove(nodes.get(ch.start_rgb))
            nodes.remove(nodes.get(ch.start_alpha))
            nodes.remove(nodes.get(ch.end_rgb))
            nodes.remove(nodes.get(ch.end_alpha))

            nodes.remove(nodes.get(ch.modifier_frame))

            try: nodes.remove(nodes.get(ch.alpha_passthrough))
            except: pass
            try: nodes.remove(nodes.get(ch.normal))
            except: pass
            try: nodes.remove(nodes.get(ch.bump))
            except: pass
            try: nodes.remove(nodes.get(ch.bump_base))
            except: pass

            # Remove modifiers
            for mod in ch.modifiers:
                tex_modifiers.delete_modifier_nodes(nodes, mod)

        # Delete the texture
        tg.textures.remove(tg.active_texture_index)

        # Set new active index
        if (tg.active_texture_index == len(tg.textures) and
            tg.active_texture_index > 0
            ):
            tg.active_texture_index -= 1
        else:
            # Force update the index to refesh paint image
            tg.active_texture_index = tg.active_texture_index

        # Refresh texture channel blend nodes
        refresh_layer_blends(group_tree)

        # Rearrange nodes
        #rearrange_nodes(group_tree)

        return {'FINISHED'}

class YAddSimpleUVs(bpy.types.Operator):
    bl_idname = "node.y_add_simple_uvs"
    bl_label = "Add simple UVs"
    bl_description = "Add Simple UVs"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == 'MESH'

    def execute(self, context):
        obj = context.object
        mesh = obj.data

        # Add simple uvs
        old_mode = obj.mode
        bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
        bpy.ops.paint.add_simple_uvs()
        bpy.ops.object.mode_set(mode=old_mode)

        return {'FINISHED'}

class YHackNormalConsistency(bpy.types.Operator):
    bl_idname = "node.y_hack_bump_consistency"
    bl_label = "Hack Normal Map Consistency"
    bl_description = "Hack bump map consistency (try this if Blender produce error normal map result)"
    #bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def execute(self, context):
        node = get_active_texture_group_node()
        group_tree = node.node_tree
        tg = group_tree.tg

        for tex in tg.textures:
            for i, ch in enumerate(tex.channels):
                if tg.channels[i].type != 'VECTOR': continue
                if ch.normal_map_type == 'BUMP':
                    ch.normal_map_type = 'NORMAL'
                    ch.normal_map_type = 'BUMP'
                else:
                    ch.normal_map_type = 'BUMP'
                    ch.normal_map_type = 'NORMAL'

        return {'FINISHED'}

def draw_tex_props(group_tree, tex, layout):

    nodes = group_tree.nodes
    tg = group_tree.tg

    source = nodes.get(tex.source)
    title = source.bl_idname.replace('ShaderNodeTex', '')

    col = layout.column()
    #col.label(title + ' Properties:')
    #col.separator()

    if title == 'Brick':
        row = col.row()
        col = row.column(align=True)
        col.label('Offset:')
        col.label('Frequency:')
        col.separator()

        col.label('Squash:')
        col.label('Frequency:')
        col.separator()

        col.label('Color 1:')
        col.label('Color 2:')
        col.label('Mortar:')
        col.separator()
        col.label('Scale:')
        col.label('Mortar Size:')
        col.label('Mortar Smooth:')
        col.label('Bias:')
        col.label('Brick Width:')
        col.label('Brick Height:')

        col = row.column(align=True)
        col.prop(source, 'offset', text='')
        col.prop(source, 'offset_frequency', text='')
        col.separator()

        col.prop(source, 'squash', text='')
        col.prop(source, 'squash_frequency', text='')
        col.separator()
        for i in range (1,10):
            if i == 4: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Checker':

        row = col.row()
        col = row.column(align=True)
        col.label('Color 1:')
        col.label('Color 2:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        for i in range (1,4):
            if i == 3: col.separator()
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Gradient':

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col = row.column(align=True)
        col.prop(source, 'gradient_type', text='')

    elif title == 'Magic':

        row = col.row()
        col = row.column(align=True)
        col.label('Depth:')
        col.label('Scale:')
        col.label('Distortion:')
        col = row.column(align=True)
        col.prop(source, 'turbulence_depth', text='')
        col.prop(source.inputs[1], 'default_value', text='')
        col.prop(source.inputs[2], 'default_value', text='')

    elif title == 'Noise':

        row = col.row()
        col = row.column(align=True)
        col.label('Scale:')
        col.label('Detail:')
        col.label('Distortion:')
        col = row.column(align=True)
        for i in range (1,4):
            col.prop(source.inputs[i], 'default_value', text='')

    elif title == 'Voronoi':

        row = col.row()
        col = row.column(align=True)
        col.label('Coloring:')
        col.separator()
        col.label('Scale:')
        col = row.column(align=True)
        col.prop(source, 'coloring', text='')
        col.separator()
        col.prop(source.inputs[1], 'default_value', text='')

    elif title == 'Wave':

        row = col.row()
        col = row.column(align=True)
        col.label('Type:')
        col.label('Profile:')
        col.label('Scale:')
        col.label('Distortion:')
        col.label('Detail:')
        col.label('Detail Scale:')
        col = row.column(align=True)
        col.prop(source, 'wave_type', text='')
        col.prop(source, 'wave_profile', text='')
        col.separator()
        for i in range (1,5):
            col.prop(source.inputs[i], 'default_value', text='')

#class YPopupMenu(bpy.types.Operator):
#    bl_idname = "node.y_popup_menu"
#    bl_label = "Popup menu"
#    bl_description = 'Popup menu'
#
#    name = StringProperty(default='Ewsom')
#
#    @classmethod
#    def poll(cls, context):
#        return get_active_texture_group_node()
#
#    #@staticmethod
#    def draw(self, context):
#        node = get_active_texture_group_node()
#        #self.layout.prop(context.scene, 'name')
#        self.layout.prop(self, 'name')
#        #draw_tex_props(node.node_tree, context.texture, self.layout)
#
#    def invoke(self, context, event):
#        #context.window_manager.invoke_popup(self)
#        return context.window_manager.invoke_popup(self)
#        #return context.window_manager.invoke_props_dialog(self)
#        #wm.popup_menu(self.draw_func, title="THE TITLE", icon="INFO")
#        #context.window_manager.popup_menu(self.draw)
#        #context.window_manager.popup_menu_pie(self.draw)
#        #return {'RUNNING_MODAL'}
#
#    def check(self, context):
#        #self.execute(context)
#        return True
#
#    def execute(self, context):
#        #context.window_manager.invoke_props_dialog(self)
#    #    popup_main(context)
#        #print('Something happen!')
#        context.scene.name = self.name
#        return {'FINISHED'}

class NODE_PT_y_texture_groups(bpy.types.Panel):
    #bl_space_type = 'VIEW_3D'
    bl_space_type = 'NODE_EDITOR'
    bl_label = "Texture Groups"
    bl_region_type = 'UI'
    #bl_region_type = 'TOOLS'
    #bl_category = "Texture Groups"

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == 'CYCLES' and context.space_data.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        obj = context.object
        is_a_mesh = True if obj and obj.type == 'MESH' else False
        node = get_active_texture_group_node()

        layout = self.layout

        if not node:
            layout.label("No texture group node selected!")
            return

        group_tree = node.node_tree
        nodes = group_tree.nodes
        tg = group_tree.tg
        #layout.context_pointer_set('group_node', node)
        #layout.context_pointer_set('tg', tg)

        icon = 'TRIA_DOWN' if tg.show_channels else 'TRIA_RIGHT'
        row = layout.row(align=True)
        row.prop(tg, 'show_channels', emboss=False, text='', icon=icon)
        row.label('Channels')

        if tg.show_channels:

            box = layout.box()
            col = box.column()
            row = col.row()
            row.template_list("NODE_UL_y_texture_groups", "", tg,
                    "channels", tg, "active_channel_index", rows=4, maxrows=5)  
            rcol = row.column(align=True)
            rcol.operator_menu_enum("node.y_add_new_texture_group_channel", 'type', icon='ZOOMIN', text='')
            rcol.operator("node.y_remove_texture_group_channel", icon='ZOOMOUT', text='')
            rcol.operator("node.y_move_texture_group_channel", text='', icon='TRIA_UP').direction = 'UP'
            rcol.operator("node.y_move_texture_group_channel", text='', icon='TRIA_DOWN').direction = 'DOWN'

            pcol = col.column()

            if tg.preview_mode: pcol.alert = True
            pcol.prop(tg, 'preview_mode', text='Preview Mode', icon='RESTRICT_VIEW_OFF')

            if len(tg.channels) > 0:

                mcol = col.column(align=True)

                channel = tg.channels[tg.active_channel_index]
                mcol.context_pointer_set('channel', channel)

                icon = 'TRIA_DOWN' if tg.show_end_modifiers else 'TRIA_RIGHT'
                row = mcol.row(align=True)
                row.label(channel.name + ' Properties:')
                row.prop(tg, 'show_end_modifiers', text='', icon=icon)
                if tg.show_end_modifiers:
                    bbox = mcol.box()
                    bcol = bbox.column()

                    inp = node.inputs[channel.io_index]
                    brow = bcol.row(align=True)
                    if channel.type == 'RGB':
                        brow.label('Background:')
                    elif channel.type == 'VALUE':
                        brow.label('Base Value:')
                    elif channel.type == 'VECTOR':
                        brow.label('Base Vector:')

                    brow.prop(inp,'default_value', text='')
                    if channel.type == 'RGB':
                        brow = bcol.row(align=True)
                        brow.label('Alpha:')
                        brow.prop(channel, 'alpha', text='')
                        if channel.alpha:
                            inp_alpha = node.inputs[channel.io_index+1]
                            brow.prop(inp_alpha, 'default_value', text='')

                    bcol.label('Final Modifiers:')

                    row = bcol.row()
                    row.template_list("NODE_UL_y_texture_modifiers", "", channel,
                            "modifiers", channel, "active_modifier_index", rows=4, maxrows=5)  

                    rcol = row.column(align=True)

                    rcol.menu("NODE_MT_y_texture_modifier_specials", icon='ZOOMIN', text='')

                    op = rcol.operator('node.y_remove_texture_modifier', icon='ZOOMOUT', text='')
                    op.parent_type = 'CHANNEL'

                    op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_UP', text='')
                    op.direction = 'UP'
                    op.parent_type = 'CHANNEL'

                    op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_DOWN', text='')
                    op.direction = 'DOWN'
                    op.parent_type = 'CHANNEL'

                    if len(channel.modifiers) > 0:
                        mod = channel.modifiers[channel.active_modifier_index]
                        tex_modifiers.draw_modifier_properties(context, channel, nodes, mod, bcol)

        icon = 'TRIA_DOWN' if tg.show_textures else 'TRIA_RIGHT'
        row = layout.row(align=True)
        row.prop(tg, 'show_textures', emboss=False, text='', icon=icon)
        row.label('Textures')

        if tg.show_textures:

            box = layout.box()

            # Check if uv is found
            uv_found = False
            if is_a_mesh and len(obj.data.uv_textures) > 0: 
                uv_found = True

            if is_a_mesh and not uv_found:
                row = box.row(align=True)
                row.alert = True
                row.operator("node.y_add_simple_uvs", icon='ERROR')
                row.alert = False
                return

            # Get texture, image and set context pointer
            tex = None
            source = None
            image = None
            if len(tg.textures) > 0:
                tex = tg.textures[tg.active_texture_index]
                box.context_pointer_set('texture', tex)

                source = nodes.get(tex.source)
                if tex.type == 'ShaderNodeTexImage':
                    image = source.image
                    box.context_pointer_set('image', image)

            col = box.column()

            row = col.row()
            row.template_list("NODE_UL_y_texture_layers", "", tg,
                    "textures", tg, "active_texture_index", rows=5, maxrows=5)  

            rcol = row.column(align=True)
            #rcol.operator_menu_enum("node.y_new_texture_layer", 'type', icon='ZOOMIN', text='')
            #rcol.context_pointer_set('group_node', node)
            rcol.menu("NODE_MT_y_new_texture_layer_menu", text='', icon='ZOOMIN')
            rcol.operator("node.y_remove_texture_layer", icon='ZOOMOUT', text='')
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_UP').direction = 'UP'
            rcol.operator("node.y_move_texture_layer", text='', icon='TRIA_DOWN').direction = 'DOWN'
            rcol.menu("NODE_MT_y_texture_specials", text='', icon='DOWNARROW_HLT')

            col = box.column()

            if tex:

                col.active = tex.enable

                ccol = col.column(align=True)
                row = ccol.row(align=True)
                
                if image:
                    #row.prop(source, "image", text='')
                    #row.prop_search(source, "image", bpy.data, 'images', text='')
                    row.template_ID(source, "image",
                            #open='paint.yp_open_paint_texture_from_file', 
                            unlink='node.y_remove_texture_layer')
                    row.operator("node.y_reload_image", text="", icon='FILE_REFRESH')
                else:
                    title = source.bl_idname.replace('ShaderNodeTex', '')
                    row.label(title + ' Properties:', icon='TEXTURE')
                    #row.label(tex.name, icon='TEXTURE')
                    #row.prop(tg, 'show_texture_properties', emboss=False, text='', icon=icon)

                icon = 'TRIA_DOWN' if tg.show_texture_properties else 'TRIA_RIGHT'
                row.prop(tg, 'show_texture_properties', text='', icon=icon)

                #rrow = row.row(align=True)
                #rrow.context_pointer_set('texture', tex)
                #rrow.operator('node.y_popup_menu', text='', icon='SCRIPTWIN')

                if tg.show_texture_properties:
                    bbox = ccol.box()
                    if not image:
                        draw_tex_props(group_tree, tex, bbox)
                    else:
                        incol = bbox.column()
                        if image.source == 'GENERATED':
                            incol.label('Generated image settings:')
                            row = incol.row()

                            col1 = row.column(align=True)
                            col1.prop(image, 'generated_width', text='X')
                            col1.prop(image, 'generated_height', text='Y')

                            col1.prop(image, 'use_generated_float', text='Float Buffer')
                            col2 = row.column(align=True)
                            col2.prop(image, 'generated_type', expand=True)

                            row = incol.row()
                            row.label('Color:')
                            row.prop(image, 'generated_color', text='')
                            incol.template_colorspace_settings(image, "colorspace_settings")

                        elif image.source == 'FILE':
                            if not image.filepath:
                                incol.label('Image Path: -')
                            else:
                                incol.label('Path: ' + image.filepath)

                            image_format = 'RGBA'
                            image_bit = int(image.depth/4)
                            if image.depth in {24, 48, 96}:
                                image_format = 'RGB'
                                image_bit = int(image.depth/3)

                            incol.label('Info: ' + str(image.size[0]) + ' x ' + str(image.size[1]) +
                                    ' ' + image_format + ' ' + str(image_bit) + '-bit')

                            incol.template_colorspace_settings(image, "colorspace_settings")
                            #incol.prop(image, 'use_view_as_render')
                            incol.prop(image, 'alpha_mode')
                            incol.prop(image, 'use_alpha')
                            #incol.prop(image, 'use_fields')
                            #incol.template_image(tex, "image", tex.image_user)
                        #ccol = bbox.column()
                        #ccol.operator("node.y_reload_image", icon='FILE_REFRESH')

                ccol.separator()

                #ccol = col.column(align=True)
                #col.label('Channels:')

                if len(tex.channels) == 0:
                    col.label('No channel found!', icon='ERROR')

                for i, ch in enumerate(tex.channels):

                    group_ch = tg.channels[i]

                    ccol = col.column(align=True)
                    ccol.context_pointer_set('channel', ch)

                    row = ccol.row(align=True)
                    row.label(tg.channels[i].name + ':') #, icon='LINK')

                    row.prop(ch, 'enable', text='')

                    row = row.row(align=True)
                    row.active = ch.enable

                    if group_ch.type == 'VECTOR':
                        row.prop(ch, 'vector_blend', text='')
                    else:
                        #blend = nodes.get(ch.blend)
                        #row.prop(blend, 'blend_type', text='')
                        row.prop(ch, 'blend_type', text='')

                    intensity = nodes.get(ch.intensity)
                    row.prop(intensity.inputs[0], 'default_value', text='')

                    row.prop(tg.channels[i], 'show_modifiers', text='', icon='MODIFIER')

                    if tg.channels[i].show_modifiers:
                        bbox = ccol.box()
                        #bbox.alert = True
                        bbox.active = ch.enable
                        bcol = bbox.column()
                        #bcol = bbox.column(align

                        if group_ch.type == 'VECTOR':
                            #row = bcol.row(align=True)
                            #row.label('Norma:')
                            #row.prop(ch, 'tex_input', text='')
                            #row.prop(ch, 'color_space', text='')
                            bcol.prop(ch, 'normal_map_type')
                            if ch.normal_map_type == 'BUMP':
                                bump = nodes.get(ch.bump)
                                #bcol.prop(bump.inputs[1], 'default_value', text='Distance')
                                bcol.prop(ch, 'bump_base_value', text='Bump Base')
                                bcol.prop(ch, 'bump_distance', text='Distance')

                        #row = bcol.row(align=True)
                        #row.label('Input:')
                        #row.prop(ch, 'tex_input', text='')
                        #row.prop(ch, 'color_space', text='')
                        if tex.type != 'ShaderNodeTexImage':
                            bcol.prop(ch, 'tex_input', text='Input')

                        row = bcol.row(align=True)
                        #crow = row.column(align=True)
                        row.label('Modifiers:')
                        #crow.label('Color Space:')
                        #crow = row.column(align=True)
                        #row.prop(ch, 'tex_input', text='')
                        #row.prop(ch, 'color_space', text='')

                        #bcol.label(tg.channels[i].name + ' Modifiers:')
                        #bcol.label('Modifiers:')

                        row = bcol.row()
                        row.template_list("NODE_UL_y_texture_modifiers", "", ch,
                                "modifiers", ch, "active_modifier_index", rows=4, maxrows=5)  

                        rcol = row.column(align=True)

                        rcol.menu("NODE_MT_y_texture_modifier_specials", icon='ZOOMIN', text='')

                        op = rcol.operator('node.y_remove_texture_modifier', icon='ZOOMOUT', text='')
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_UP', text='')
                        op.direction = 'UP'
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        op = rcol.operator('node.y_move_texture_modifier', icon='TRIA_DOWN', text='')
                        op.direction = 'DOWN'
                        op.parent_type = 'TEXTURE_CHANNEL'
                        op.channel_index = i

                        if len(ch.modifiers) > 0:

                            mod = ch.modifiers[ch.active_modifier_index]
                            tex_modifiers.draw_modifier_properties(context, ch, nodes, mod, bcol)

                        ccol.separator()

                    if i == len(tex.channels)-1: #and i > 0:
                        ccol.separator()

                ccol = col.column(align=True)

                row = ccol.row(align=True)
                split = row.split(percentage=0.26, align=True)
                split.label('Vector:')
                if is_a_mesh and tex.texcoord_type == 'UV':
                    uv_map = nodes.get(tex.uv_map)
                    ssplit = split.split(percentage=0.33, align=True)
                    ssplit.prop(tex, 'texcoord_type', text='')
                    ssplit.prop_search(uv_map, "uv_map", obj.data, "uv_textures", text='')
                else:
                    split.prop(tex, 'texcoord_type', text='')

                icon = 'TRIA_DOWN' if tg.show_vector_properties else 'TRIA_RIGHT'
                row.prop(tg, 'show_vector_properties', text='', icon=icon)

                if tg.show_vector_properties:
                    bbox = ccol.box()
                    #if tex.texcoord_type == 'UV':
                    bbox.prop(source.texture_mapping, 'translation', text='Offset')
                    bbox.prop(source.texture_mapping, 'scale')
                    #else:
                    #    bbox.label('This option has no settings yet!')
                    ccol.separator()

                ccol = col.column(align=True)

                # MASK
                #row = ccol.row(align=True)
                #row.label('Mask:')

                #icon = 'TRIA_DOWN' if tg.show_mask_properties else 'TRIA_RIGHT'
                #row.prop(tg, 'show_mask_properties', text='', icon=icon)

                #if tg.show_mask_properties:
                #    bbox = ccol.box()

                #row = tcol.row()
                #row.label('Texture Modifiers:')
                #icon = 'TRIA_DOWN' if tg.show_texture_modifiers else 'TRIA_RIGHT'
                #row.prop(tg, 'show_texture_modifiers', emboss=False, text='', icon=icon)

                #if tg.show_texture_modifiers:
                #    bbox = tcol.box()

class NODE_UL_y_texture_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        #if not group_node: return
        inputs = group_node.inputs

        row = layout.row()
        row.prop(item, 'name', text='', emboss=False, icon='LINK')
        if item.type == 'VALUE':
            row.prop(inputs[item.io_index], 'default_value', text='') #, emboss=False)
        elif item.type == 'RGB':
            rrow = row.row(align=True)
            rrow.prop(inputs[item.io_index], 'default_value', text='', icon='COLOR')
            if item.alpha:
                rrow.prop(inputs[item.io_index+1], 'default_value', text='')
        #elif item.type == 'VECTOR':
        #    row.prop(inputs[item.io_index], 'default_value', text='', expand=False)

class NODE_UL_y_texture_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        group_node = get_active_texture_group_node()
        #if not group_node: return
        tg = group_node.node_tree.tg
        nodes = group_node.node_tree.nodes

        # Get active channel
        #channel_idx = tg.active_channel_index
        #channel = tg.channels[channel_idx]

        master = layout.row(align=True)

        row = master.row(align=True)

        #if not item.enable or not item.channels[channel_idx].enable: row.active = False

        if item.type == 'ShaderNodeTexImage':
            source = nodes.get(item.source)
            image = source.image
            row.context_pointer_set('image', image)
            row.prop(image, 'name', text='', emboss=False, icon_value=image.preview.icon_id)

            # Asterisk icon to indicate dirty image and also for saving/packing
            if image.is_dirty:
                if image.packed_file or image.filepath == '':
                    row.operator('node.y_pack_image', text='', icon_value=custom_icons['asterisk'].icon_id, emboss=False)
                else: row.operator('node.y_save_image', text='', icon_value=custom_icons['asterisk'].icon_id, emboss=False)

            # Indicate packed image
            if image.packed_file:
                row.label(text='', icon='PACKAGE')

        else:
            row.prop(item, 'name', text='', emboss=False, icon='TEXTURE')

        #blend = nodes.get(item.channels[channel_idx].blend)
        #row.prop(blend, 'blend_type', text ='')

        #intensity = nodes.get(item.channels[channel_idx].intensity)
        #row.prop(intensity.inputs[0], 'default_value', text='')

        #row = master.row()
        #if item.enable: row.active = True
        #else: row.active = False
        #row.prop(item.channels[channel_idx], 'enable', text='')

        # Modifier shortcut
        shortcut_found = False
        for ch in item.channels:
            for mod in ch.modifiers:
                if mod.shortcut:
                    shortcut_found = True
                    if mod.type == 'RGB_TO_INTENSITY':
                        rgb2i_color = nodes.get(mod.rgb2i_color)
                        rrow = row.row()
                        rrow.prop(rgb2i_color.outputs[0], 'default_value', text='', icon='COLOR')
                    break
            if shortcut_found:
                break

        # Texture visibility
        row = master.row()
        if item.enable: eye_icon = 'RESTRICT_VIEW_OFF'
        else: eye_icon = 'RESTRICT_VIEW_ON'
        row.prop(item, 'enable', emboss=False, text='', icon=eye_icon)

class YNewTexMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_new_texture_layer_menu"
    bl_description = 'New Texture Layer'
    bl_label = "Texture Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def draw(self, context):
        #row = self.layout.row()
        #col = row.column()
        col = self.layout.column(align=True)
        #col.context_pointer_set('group_node', context.group_node)
        col.label('Image:')
        col.operator("node.y_new_texture_layer", text='New Image', icon='IMAGE_DATA').type = 'ShaderNodeTexImage'
        col.operator("node.y_open_image_to_layer", text='Open Image', icon='IMASEL')
        col.operator("node.y_open_available_image_to_layer", text='Open Available Image', icon='IMASEL')
        col.separator()

        #col = row.column()
        col.label('Generated:')
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Checker').type = 'ShaderNodeTexChecker'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Gradient').type = 'ShaderNodeTexGradient'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Magic').type = 'ShaderNodeTexMagic'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Noise').type = 'ShaderNodeTexNoise'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Voronoi').type = 'ShaderNodeTexVoronoi'
        col.operator("node.y_new_texture_layer", icon='TEXTURE', text='Wave').type = 'ShaderNodeTexWave'

class YTexSpecialMenu(bpy.types.Menu):
    bl_idname = "NODE_MT_y_texture_specials"
    bl_label = "Texture Special Menu"
    bl_description = "Texture Special Menu"

    @classmethod
    def poll(cls, context):
        return get_active_texture_group_node()

    def draw(self, context):
        #self.layout.context_pointer_set('space_data', context.screen.areas[6].spaces[0])
        #self.layout.operator('image.save_as', icon='FILE_TICK')
        self.layout.operator('node.y_pack_image', icon='PACKAGE')
        self.layout.operator('node.y_save_image', icon='FILE_TICK')
        if hasattr(context, 'image') and context.image.packed_file:
            self.layout.operator('node.y_save_as_image', text='Unpack As Image', icon='UGLYPACKAGE').unpack = True
        else:
            self.layout.operator('node.y_save_as_image', text='Save As Image', icon='SAVE_AS')
        self.layout.operator('node.y_save_image', text='Save/Pack All', icon='FILE_TICK')
        self.layout.separator()
        self.layout.operator('node.y_hack_bump_consistency', icon='MATCAP_23')
        #self.layout.operator("node.y_reload_image", icon='FILE_REFRESH')

def menu_func(self, context):
    if context.space_data.tree_type != 'ShaderNodeTree' or context.scene.render.engine != 'CYCLES': return
    l = self.layout
    l.operator_context = 'INVOKE_REGION_WIN'
    l.separator()
    l.operator('node.y_add_new_texture_group_node', text='Texture Group', icon='NODE')

def update_channel_name(self, context):
    group_tree = self.id_data

    if self.io_index < len(group_tree.inputs):
        group_tree.inputs[self.io_index].name = self.name
        group_tree.outputs[self.io_index].name = self.name

        if self.type == 'RGB' and self.alpha:
            group_tree.inputs[self.io_index+1].name = self.name + ' Alpha'
            group_tree.outputs[self.io_index+1].name = self.name + ' Alpha'

def update_texture_enable(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    for ch in self.channels:

        blend = nodes.get(ch.blend)
        if not blend: continue

        if self.enable and ch.enable:
            blend.mute = False
        else: blend.mute = True

def update_channel_enable(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    # Get texture
    tex = None
    for t in group_tree.tg.textures:
        for ch in t.channels:
            if ch == self:
                tex = t
                break

    blend = nodes.get(self.blend)
    if not blend: return

    if tex.enable and self.enable:
        blend.mute = False
    else: blend.mute = True

def update_tex_input(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    tg = group_tree.tg

    tex = None
    for t in tg.textures:
        for ch in t.channels:
            if ch == self:
                tex = t
                break
    if not tex: return

    source = nodes.get(tex.source)
    start_rgb = nodes.get(self.start_rgb)

    if self.tex_input == 'RGB': index = 0
    elif self.tex_input == 'ALPHA': index = 1
    else: return

    group_tree.links.new(source.outputs[index], start_rgb.inputs[0])

#def update_tex_channel_color_space(self, context):
#    group_tree = self.id_data
#    nodes = group_tree.nodes
#
#    linear = nodes.get(self.linear)
#    if not linear: return
#
#    if self.color_space == 'SRGB':
#        linear.mute = False
#    elif self.color_space == 'LINEAR':
#        linear.mute = True

def update_preview_mode(self, context):
    try:
        mat = bpy.context.object.active_material
        tree = mat.node_tree
        nodes = tree.nodes
        group_node = get_active_texture_group_node()
        tg = group_node.node_tree.tg
        channel = tg.channels[tg.active_channel_index]
        index = tg.active_channel_index
    except: return

    # Search for preview node
    preview = nodes.get('Emission Viewer')

    if self.preview_mode:

        # Search for output
        output = None
        for node in nodes:
            if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output:
                output = node
                break

        if not output: return

        # Remember output and original bsdf
        mat.tg.ori_output = output.name
        ori_bsdf = output.inputs[0].links[0].from_node

        if not preview:
            preview = nodes.new('ShaderNodeEmission')
            preview.name = 'Emission Viewer'
            preview.label = 'Preview'
            preview.hide = True
            preview.location = (output.location.x, output.location.y + 30.0)

        # Only remember original BSDF if its not the preview node itself
        if ori_bsdf != preview:
            mat.tg.ori_bsdf = ori_bsdf.name

        if channel.type == 'RGB' and channel.alpha:
            from_socket = [link.from_socket for link in preview.inputs[0].links]
            if not from_socket: 
                tree.links.new(group_node.outputs[channel.io_index], preview.inputs[0])
            else:
                from_socket = from_socket[0]
                color_output = group_node.outputs[channel.io_index]
                alpha_output = group_node.outputs[channel.io_index+1]
                if from_socket == color_output:
                    tree.links.new(alpha_output, preview.inputs[0])
                else:
                    tree.links.new(color_output, preview.inputs[0])
        else:
            tree.links.new(group_node.outputs[channel.io_index], preview.inputs[0])
        tree.links.new(preview.outputs[0], output.inputs[0])
    else:
        try: nodes.remove(preview)
        except: pass

        bsdf = nodes.get(mat.tg.ori_bsdf)
        output = nodes.get(mat.tg.ori_output)
        mat.tg.ori_bsdf = ''
        mat.tg.ori_output = ''

        try: tree.links.new(bsdf.outputs[0], output.inputs[0])
        except: pass

def update_active_group_channel(self, context):
    try: 
        group_node = get_active_texture_group_node()
        tg = group_node.node_tree.tg
    except: return
    
    if tg.preview_mode: tg.preview_mode = True

def update_texcoord_type(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes
    links = group_tree.links

    source = nodes.get(self.source)
    texcoord = nodes.get(self.texcoord)
    uv_map = nodes.get(self.uv_map)

    if self.texcoord_type == 'UV':
        links.new(uv_map.outputs[0], source.inputs[0])
    else:
        links.new(texcoord.outputs[self.texcoord_type], source.inputs[0])

def update_texture_index(self, context):
    scene = context.scene
    obj = context.object
    group_tree = self.id_data
    nodes = group_tree.nodes

    if (len(self.textures) == 0 or
        self.active_texture_index >= len(self.textures) or self.active_texture_index < 0): 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        return

    # Set image paint mode to Image
    scene.tool_settings.image_paint.mode = 'IMAGE'

    tex = self.textures[self.active_texture_index]
    if tex.type != 'ShaderNodeTexImage': 
        update_image_editor_image(context, None)
        scene.tool_settings.image_paint.canvas = None
        return

    # Get source image
    source = nodes.get(tex.source)
    if not source or not source.image: return

    # Update image editor
    update_image_editor_image(context, source.image)

    # Update tex paint
    scene.tool_settings.image_paint.canvas = source.image

    # Update uv layer
    if obj.type == 'MESH':
        uv_map = nodes.get(tex.uv_map)
        for i, uv in enumerate(obj.data.uv_textures):
            if uv.name == uv_map.uv_map:
                obj.data.uv_textures.active_index = i
                break

#def get_tex_and_channel_index_from_layer_channel(tg, channel):
#    tex = None
#    ch_index = -1
#    for t in tg.textures:
#        for i, ch in enumerate(t.channels):
#            if ch == channel:
#                tex = t
#                ch_index = i
#                break
#
#    return tex, ch_index

def update_normal_map_type(self, context):
    refresh_layer_blends(self.id_data)

def update_blend_type(self, context):
    refresh_layer_blends(self.id_data)

def update_vector_blend(self, context):
    refresh_layer_blends(self.id_data)

def update_bump_base_value(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    bump_base = nodes.get(self.bump_base)
    val = self.bump_base_value
    bump_base.inputs[1].default_value = (val, val, val, 1.0)

def update_bump_distance(self, context):
    group_tree = self.id_data
    nodes = group_tree.nodes

    bump = nodes.get(self.bump)
    bump.inputs[1].default_value = self.bump_distance

def update_channel_alpha(self, context):
    group_tree = self.id_data
    tg = group_tree.tg
    nodes = group_tree.nodes
    links = group_tree.links
    inputs = group_tree.inputs
    outputs = group_tree.outputs

    start_alpha_entry = nodes.get(self.start_alpha_entry)
    #end_alpha_entry = nodes.get(self.end_alpha_entry)
    if not start_alpha_entry: return

    start = nodes.get(tg.start)
    end = nodes.get(tg.end)
    end_alpha = nodes.get(self.end_alpha)

    alpha_io_found = False
    for out in start.outputs:
        for link in out.links:
            if link.to_socket == start_alpha_entry.inputs[0]:
                alpha_io_found = True
                break
        if alpha_io_found: break
    
    if self.alpha and not alpha_io_found:
        name = self.name + ' Alpha'
        inp = inputs.new('NodeSocketFloat', name)
        out = outputs.new('NodeSocketFloat', name)

        # Set min max
        inp.min_value = 0.0
        inp.max_value = 1.0
        inp.default_value = 0.0

        last_index = len(inputs)-1
        alpha_index = self.io_index+1

        inputs.move(last_index, alpha_index)
        outputs.move(last_index, alpha_index)

        links.new(start.outputs[alpha_index], start_alpha_entry.inputs[0])
        links.new(end_alpha.outputs[0], end.inputs[alpha_index])
        
        # Set node default_value
        node = get_active_texture_group_node()
        node.inputs[alpha_index].default_value = 0.0

        # Shift other IO index
        for ch in tg.channels:
            if ch.io_index >= alpha_index:
                ch.io_index += 1

    elif not self.alpha and alpha_io_found:

        inputs.remove(inputs[self.io_index+1])
        outputs.remove(outputs[self.io_index+1])

        # Relink
        solid_alpha = nodes.get(self.solid_alpha)
        links.new(solid_alpha.outputs[0], start_alpha_entry.inputs[0])

        # Shift other IO index
        for ch in tg.channels:
            if ch.io_index > self.io_index:
                ch.io_index -= 1

class YLayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    tex_input = EnumProperty(
            name = 'Input from Texture',
            items = (('RGB', 'Color', ''),
                     ('ALPHA', 'Alpha / Factor', '')),
            default = 'RGB',
            update = update_tex_input)

    #color_space = EnumProperty(
    #        name = 'Input Color Space',
    #        items = (('LINEAR', 'Linear', ''),
    #                 ('SRGB', 'sRGB', '')),
    #        default = 'LINEAR',
    #        update = update_tex_channel_color_space)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            items = normal_map_type_items,
            default = 'BUMP',
            update = update_normal_map_type)

    blend_type = EnumProperty(
        name = 'Blend',
        #items = vector_and_blend_type_items)
        items = blend_type_items,
        default = 'MIX',
        update = update_blend_type)

    vector_blend = EnumProperty(
            name = 'Vector Blend Type',
            items = vector_blend_items,
            default = 'MIX',
            update = update_vector_blend)

    modifiers = CollectionProperty(type=tex_modifiers.YTextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    #linear = StringProperty(default='')
    blend = StringProperty(default='')
    alpha_passthrough = StringProperty(default='')
    intensity = StringProperty(default='')

    # Modifier pipeline
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    # Normal related
    bump_base = StringProperty(default='')
    bump = StringProperty(default='')
    normal = StringProperty(default='')

    bump_distance = FloatProperty(
            name='Bump Distance', 
            description= 'Distance of bump', 
            default=0.05, min=-1.0, max=1.0,
            update=update_bump_distance)

    bump_base_value = FloatProperty(
            name='Bump Base', 
            description= 'Base value of bump map', 
            default=0.5, min=0.0, max=1.0,
            update=update_bump_base_value)

    modifier_frame = StringProperty(default='')

class YTextureLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    enable = BoolProperty(default=True, update=update_texture_enable)
    channels = CollectionProperty(type=YLayerChannel)

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'ShaderNodeTexImage')

    texcoord_type = EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_texcoord_type)

    # Node names
    source = StringProperty(default='')
    #linear = StringProperty(default='')
    solid_alpha = StringProperty(default='')
    #uv = StringProperty(default='')

    texcoord = StringProperty(default='')
    uv_map = StringProperty(default='')

    source_frame = StringProperty(default='')
    blend_frame = StringProperty(default='')

class YGroupChannel(bpy.types.PropertyGroup):
    name = StringProperty(
            name='Channel Name', 
            description = 'Name of the channel',
            default='Albedo',
            update=update_channel_name)

    type = EnumProperty(
            name = 'Channel Type',
            items = (('VALUE', 'Value', ''),
                     ('RGB', 'RGB', ''),
                     ('VECTOR', 'Vector', '')),
            default = 'RGB')

    #is_alpha_channel = BoolProperty(default=False)
    #input_index = IntProperty(default=-1)
    #output_index = IntProperty(default=-1)
    #input_alpha_index = IntProperty(default=-1)
    #output_alpha_index = IntProperty(default=-1)

    io_index = IntProperty(default=0)
    alpha = BoolProperty(default=False, update=update_channel_alpha)

    modifiers = CollectionProperty(type=tex_modifiers.YTextureModifier)
    active_modifier_index = IntProperty(default=0)

    # Node names
    start_linear = StringProperty(default='')
    start_convert = StringProperty(default='')
    start_entry = StringProperty(default='')
    start_alpha_entry = StringProperty(default='')
    solid_alpha = StringProperty(default='')

    end_entry = StringProperty(default='')
    end_alpha_entry = StringProperty(default='')
    end_linear = StringProperty(default='')
    end_convert = StringProperty(default='')

    # For modifiers
    start_rgb = StringProperty(default='')
    start_alpha = StringProperty(default='')
    end_rgb = StringProperty(default='')
    end_alpha = StringProperty(default='')

    modifier_frame = StringProperty(default='')

    # UI related
    show_modifiers = BoolProperty(default=False)

class YTextureGroup(bpy.types.PropertyGroup):
    is_tg_node = BoolProperty(default=False)

    # Channels
    channels = CollectionProperty(type=YGroupChannel)
    active_channel_index = IntProperty(default=0, update=update_active_group_channel)

    # Textures
    textures = CollectionProperty(type=YTextureLayer)
    active_texture_index = IntProperty(default=0, update=update_texture_index)

    # Node names
    start = StringProperty(default='')
    start_frame = StringProperty(default='')

    end = StringProperty(default='')
    end_entry_frame = StringProperty(default='')
    end_linear_frame = StringProperty(default='')

    # Temp channels to remember last channel selected when adding new texture
    #temp_channels = CollectionProperty(type=YTempChannel)

    # UI related
    show_channels = BoolProperty(default=True)
    show_textures = BoolProperty(default=True)
    show_texture_properties = BoolProperty(default=False)
    show_end_modifiers = BoolProperty(default=False)
    show_vector_properties = BoolProperty(default=False)
    show_mask_properties = BoolProperty(default=False)

    preview_mode = BoolProperty(default=False, update=update_preview_mode)

    # Useful to suspend update when adding new stuff
    halt_update = BoolProperty(default=False)

class YMaterialTGProps(bpy.types.PropertyGroup):
    ori_bsdf = StringProperty(default='')
    ori_output = StringProperty(default='')

@persistent
def load_libraries(scene):
    # Node groups necessary are in nodegroups_lib.blend
    filepath = get_addon_filepath() + "lib.blend"

    with bpy.data.libraries.load(filepath) as (data_from, data_to):

        # Load node groups
        exist_groups = [ng.name for ng in bpy.data.node_groups]
        for ng in data_from.node_groups:
            if ng not in exist_groups:
                data_to.node_groups.append(ng)

def register():
    # Custom Icon
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    custom_icons.load('asterisk', get_addon_filepath() + 'asterisk_icon.png', 'IMAGE')

    # Register classes
    bpy.utils.register_module(__name__)

    # TG Props
    bpy.types.ShaderNodeTree.tg = PointerProperty(type=YTextureGroup)
    bpy.types.Material.tg = PointerProperty(type=YMaterialTGProps)

    # UI panel
    bpy.types.NODE_MT_add.append(menu_func)

    # Load libraries
    bpy.app.handlers.load_post.append(load_libraries)

def unregister():
    # Custom Icon
    global custom_icons
    bpy.utils.previews.remove(custom_icons)

    # Remove UI panel
    bpy.types.NODE_MT_add.remove(menu_func)

    # Remove classes
    bpy.utils.unregister_module(__name__)

    # Remove libraries
    bpy.app.handlers.load_post.remove(load_libraries)

if __name__ == "__main__":
    register()
