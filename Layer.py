import bpy, time, re
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import Modifier, lib, Blur
from .common import *
from .node_arrangements import *
from .node_connections import *
from .subtree import *

DEFAULT_NEW_IMG_SUFFIX = ' Tex'

texture_node_bl_idnames = {
        'IMAGE' : 'ShaderNodeTexImage',
        'ENVIRONMENT' : 'ShaderNodeTexEnvironment',
        'BRICK' : 'ShaderNodeTexBrick',
        'CHECKER' : 'ShaderNodeTexChecker',
        'GRADIENT' : 'ShaderNodeTexGradient',
        'MAGIC' : 'ShaderNodeTexMagic',
        'MUSGRAVE' : 'ShaderNodeTexMusgrave',
        'NOISE' : 'ShaderNodeTexNoise',
        'POINT_DENSITY' : 'ShaderNodeTexPointDensity',
        'SKY' : 'ShaderNodeTexSky',
        'VORONOI' : 'ShaderNodeTexVoronoi',
        'WAVE' : 'ShaderNodeTexWave',
        }

def create_texture_channel_nodes(group_tree, texture, channel):

    tl = group_tree.tl
    #nodes = group_tree.nodes

    ch_index = [i for i, c in enumerate(texture.channels) if c == channel][0]
    root_ch = tl.channels[ch_index]

    #tree = nodes.get(texture.group_node).node_tree
    tree = texture.tree

    # Tree input and output
    inp = tree.inputs.new(channel_socket_input_bl_idnames[root_ch.type], root_ch.name)
    out = tree.outputs.new(channel_socket_output_bl_idnames[root_ch.type], root_ch.name)
    if root_ch.alpha:
        inp = tree.inputs.new(channel_socket_input_bl_idnames['VALUE'], root_ch.name + ' Alpha')
        out = tree.outputs.new(channel_socket_output_bl_idnames['VALUE'], root_ch.name + ' Alpha')

    # Modifier pipeline nodes
    start_rgb = tree.nodes.new('NodeReroute')
    start_rgb.label = 'Start RGB'
    channel.start_rgb = start_rgb.name

    start_alpha = tree.nodes.new('NodeReroute')
    start_alpha.label = 'Start Alpha'
    channel.start_alpha = start_alpha.name

    end_rgb = tree.nodes.new('NodeReroute')
    end_rgb.label = 'End RGB'
    channel.end_rgb = end_rgb.name

    end_alpha = tree.nodes.new('NodeReroute')
    end_alpha.label = 'End Alpha'
    channel.end_alpha = end_alpha.name

    # Intensity nodes
    intensity = tree.nodes.new('ShaderNodeMixRGB')
    intensity.label = 'Intensity'
    intensity.inputs[0].default_value = 1.0
    intensity.inputs[1].default_value = (0,0,0,1)
    intensity.inputs[2].default_value = (1,1,1,1)
    channel.intensity = intensity.name

    # Normal nodes
    #if root_ch.type == 'NORMAL':
    #    normal = tree.nodes.new('ShaderNodeNormalMap')
    #    uv_map = tree.nodes.get(texture.uv_map)
    #    normal.uv_map = uv_map.uv_map
    #    channel.normal = normal.name

    #    bump_base = tree.nodes.new('ShaderNodeMixRGB')
    #    bump_base.label = 'Bump Base'
    #    bump_base.inputs[1].default_value = (0.5, 0.5, 0.5, 1.0)
    #    channel.bump_base = bump_base.name

    #    bump = tree.nodes.new('ShaderNodeBump')
    #    bump.inputs[1].default_value = 0.05
    #    channel.bump = bump.name

    #    normal_flip = tree.nodes.new('ShaderNodeGroup')
    #    normal_flip.node_tree = lib.get_node_tree_lib(lib.FLIP_BACKFACE_NORMAL)
    #    normal_flip.label = 'Flip Backface Normal'
    #    channel.normal_flip = normal_flip.name

    # Update texture channel blend type
    update_blend_type_(root_ch, texture, channel)

    # Reconnect node inside textures
    reconnect_tex_nodes(texture, ch_index)

def update_image_editor_image(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if not area.spaces[0].use_image_pin:
                area.spaces[0].image = image

def channel_items(self, context):
    node = get_active_texture_layers_node()
    tl = node.node_tree.tl

    items = []

    for i, ch in enumerate(tl.channels):
        if ch.type == 'RGB':
            icon_name = 'rgb_channel'
        elif ch.type == 'VALUE':
            icon_name = 'value_channel'
        elif ch.type == 'NORMAL':
            icon_name = 'vector_channel'
        items.append((str(i), ch.name, '', lib.custom_icons[icon_name].icon_id, i))

    items.append(('-1', 'All Channels', '', lib.custom_icons['channels'].icon_id, len(items)))

    return items

def tex_input_items(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    if not m: return []
    #tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]

    items = []

    if root_ch.colorspace == 'SRGB':
        items.append(('RGB_LINEAR', 'Color (Linear)', ''))
        items.append(('RGB_SRGB', 'Color (Gamma)',  ''))
    else: items.append(('RGB_LINEAR', 'Color', ''))
        
    items.append(('ALPHA', 'Factor',  ''))

    return items

def add_new_texture(tex_name, tex_type, channel_idx, blend_type, normal_blend, normal_map_type, 
        texcoord_type, uv_map_name='', image=None, add_rgb_to_intensity=False, rgb_to_intensity_color=(1,1,1)):

    group_node = get_active_texture_layers_node()
    group_tree = group_node.node_tree
    nodes = group_tree.nodes
    links = group_tree.links
    tl = group_tree.tl

    # Add texture to group
    tex = tl.textures.add()
    tex.type = tex_type
    tex.name = tex_name
    tex.uv_name = uv_map_name

    if image:
        tex.image_name = image.name

    # Move new texture to current index
    last_index = len(tl.textures)-1
    index = tl.active_texture_index
    tl.textures.move(last_index, index)
    tex = tl.textures[index] # Repoint to new index

    # Repoint other texture index for other texture channels
    for i in range(index+1, last_index+1):
        for c in tl.textures[i].channels:
            c.texture_index = i

    # New texture node group
    group_node = nodes.new('ShaderNodeGroup')
    tex.group_node = group_node.name

    # New texture tree
    tree = bpy.data.node_groups.new(TEXGROUP_PREFIX + tex_name, 'ShaderNodeTree')
    tree.tl.is_tl_tex_node = True
    tree.tl.version = get_current_version_str()
    group_node.node_tree = tree
    tex.tree = tree
    #nodes = tree.nodes

    # Create info nodes
    create_info_nodes(group_tree, tex)

    # Tree start and end
    start = tree.nodes.new('NodeGroupInput')
    tex.start = start.name
    end = tree.nodes.new('NodeGroupOutput')
    tex.end = end.name

    # Add source frame
    source = tree.nodes.new(texture_node_bl_idnames[tex_type])
    source.label = 'Source'
    tex.source = source.name

    if tex_type == 'IMAGE':
        # Always set non color to image node because of linear pipeline
        source.color_space = 'NONE'

        # Add new image if it's image texture
        source.image = image
    else:
        # Solid alpha for non image texture
        solid_alpha = tree.nodes.new('ShaderNodeValue')
        solid_alpha.label = 'Solid Alpha'
        solid_alpha.outputs[0].default_value = 1.0
        tex.solid_alpha = solid_alpha.name

    # Add geometry node
    geometry = tree.nodes.new('ShaderNodeNewGeometry')
    geometry.label = 'Source Geometry'
    tex.geometry = geometry.name

    # Add texcoord node
    texcoord = tree.nodes.new('ShaderNodeTexCoord')
    texcoord.label = 'Source TexCoord'
    tex.texcoord = texcoord.name

    # Add uv map node
    uv_map = tree.nodes.new('ShaderNodeUVMap')
    uv_map.label = 'Source UV Map'
    uv_map.uv_map = uv_map_name
    tex.uv_map = uv_map.name

    # Add tangent node
    tangent = tree.nodes.new('ShaderNodeNormalMap')
    tangent.label = 'Source Tangent'
    tangent.uv_map = uv_map_name
    tangent.inputs[1].default_value = (1.0, 0.5, 0.5, 1.0)
    tex.tangent = tangent.name

    bitangent = tree.nodes.new('ShaderNodeNormalMap')
    bitangent.label = 'Source Bitangent'
    bitangent.uv_map = uv_map_name
    bitangent.inputs[1].default_value = (0.5, 1.0, 0.5, 1.0)
    tex.bitangent = bitangent.name

    # Set tex coordinate type
    tex.texcoord_type = texcoord_type

    ## Add channels
    shortcut_created = False
    for i, ch in enumerate(tl.channels):
        # Add new channel to current texture
        c = tex.channels.add()
        c.channel_index = i
        c.texture_index = index

        # Add blend and other nodes
        create_texture_channel_nodes(group_tree, tex, c)

        # Set some props to selected channel
        if channel_idx == i or channel_idx == -1:
            c.enable = True
            if ch.type == 'NORMAL':
                c.normal_blend = normal_blend
            else:
                c.blend_type = blend_type
        else: 
            c.enable = False

        if ch.type == 'NORMAL':
            c.normal_map_type = normal_map_type

        if add_rgb_to_intensity:

            # If RGB to intensity is selected, bump base is better be 0.0
            if ch.type == 'NORMAL':
                c.bump_base_value = 0.0

            m = Modifier.add_new_modifier(c, 'RGB_TO_INTENSITY')
            m.texture_index = index
            if channel_idx == i or channel_idx == -1:
                col = (rgb_to_intensity_color[0], rgb_to_intensity_color[1], rgb_to_intensity_color[2], 1)
                rgb2i = tex.tree.nodes.get(m.rgb2i)
                rgb2i.inputs[2].default_value = col

            if c.enable and ch.type == 'RGB' and not shortcut_created:
                m.shortcut = True
                shortcut_created = True

    # Refresh paint image by updating the index
    tl.active_texture_index = index

    # Rearrange node inside textures
    rearrange_tex_nodes(tex)

    return tex

def update_channel_idx_new_texture(self, context):
    node = get_active_texture_layers_node()
    tl = node.node_tree.tl

    if self.channel_idx == '-1':
        self.rgb_to_intensity_color = (1,1,1)
        return

    for i, ch in enumerate(tl.channels):
        if self.channel_idx == str(i):
            if ch.type == 'RGB':
                self.rgb_to_intensity_color = (1,0,1)
            else: self.rgb_to_intensity_color = (1,1,1)

class YNewTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_new_texture_layer"
    bl_label = "New Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'IMAGE')

    # For image texture
    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)
    color = FloatVectorProperty(name='Color', size=4, subtype='COLOR', default=(0.0,0.0,0.0,0.0), min=0.0, max=1.0)
    #alpha = BoolProperty(name='Alpha', default=True)
    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    channel_idx = EnumProperty(
            name = 'Channel',
            description = 'Channel of new texture layer, can be changed later',
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    uv_map = StringProperty(default='')

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'BUMP_MAP')

    @classmethod
    def poll(cls, context):
        return get_active_texture_layers_node()
        #return hasattr(context, 'group_node') and context.group_node

    def invoke(self, context, event):

        #self.group_node = node = context.group_node
        #print(self.group_node)
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        #tl = context.group_node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

        if self.type != 'IMAGE':
            name = [i[1] for i in texture_type_items if i[0] == self.type][0]
            items = tl.textures
        else:
            name = obj.active_material.name + DEFAULT_NEW_IMG_SUFFIX
            items = bpy.data.images

        self.name = get_unique_name(name, items)

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_textures) > 0:
            self.uv_map = obj.data.uv_textures.active.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        #tl = self.group_node.node_tree.tl
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        if len(tl.channels) == 0:
            self.layout.label('No channel found! Still want to create a texture?', icon='ERROR')
            return

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        row = self.layout.split(percentage=0.4)
        col = row.column(align=False)

        col.label('Name:')
        col.label('Channel:')
        if channel and channel.type == 'NORMAL':
            col.label('Type:')
        col.label('')

        if self.add_rgb_to_intensity:
            col.label('RGB To Intensity Color:')

        if self.type == 'IMAGE':
            if not self.add_rgb_to_intensity:
                col.label('Color:')
            col.label('')
            col.label('Width:')
            col.label('Height:')

        col.label('Vector:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')

        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

        if self.type == 'IMAGE':
            if not self.add_rgb_to_intensity:
                col.prop(self, 'color', text='')
                #col.prop(self, 'alpha')
            col.prop(self, 'hdr')
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

    def execute(self, context):

        T = time.time()

        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        tlui = context.window_manager.tlui

        # Check if texture with same name is already available
        same_name = [t for t in tl.textures if t.name == self.name]
        if same_name:
            self.report({'ERROR'}, "Texture named '" + tex_name +"' is already available!")
            return {'CANCELLED'}

        img = None
        if self.type == 'IMAGE':
            alpha = False if self.add_rgb_to_intensity else True
            color = (0,0,0,1) if self.add_rgb_to_intensity else self.color
            img = bpy.data.images.new(self.name, self.width, self.height, alpha, self.hdr)
            #img.generated_type = self.generated_type
            img.generated_type = 'BLANK'
            img.generated_color = color
            img.use_alpha = False if self.add_rgb_to_intensity else True
            update_image_editor_image(context, img)

        tl.halt_update = True
        tex = add_new_texture(self.name, self.type, int(self.channel_idx), self.blend_type, self.normal_blend, 
                self.normal_map_type, self.texcoord_type, self.uv_map, img, 
                self.add_rgb_to_intensity, self.rgb_to_intensity_color)
        tl.halt_update = False

        # Some texture type better be at sRGB colorspace
        if tex.type in {'CHECKER'}:
            for i, root_ch in enumerate(tl.channels):
                if root_ch.colorspace == 'SRGB':
                    tex.channels[i].tex_input = 'RGB_SRGB'

        # Reconnect and rearrange nodes
        reconnect_tl_tex_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        if self.type != 'IMAGE':
            tlui.tex_ui.expand_content = True
        tlui.need_update = True

        print('INFO: Texture', tex.name, 'is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

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
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'OVERLAY')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'NORMAL_MAP')

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_layers_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

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
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        
        row = self.layout.row()

        col = row.column()
        col.label('Vector:')
        col.label('Channel:')
        if channel and channel.type == 'NORMAL':
            col.label('Type:')

        if self.add_rgb_to_intensity:
            col.label('')
            col.label('RGB2I Color:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        #col.label('')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

        self.layout.prop(self, 'relative')

    def execute(self, context):
        node = get_active_texture_layers_node()

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        node.node_tree.tl.halt_update = True

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            add_new_texture(image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                    self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map,
                    image, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.tl.halt_update = False

        # Reconnect and rearrange nodes
        reconnect_tl_tex_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

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
            items = channel_items,
            update=update_channel_idx_new_texture)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MIX')

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX')

    add_rgb_to_intensity = BoolProperty(
            name = 'Add RGB To Intensity',
            description = 'Add RGB To Intensity modifier to all channels of newly created texture layer',
            default=False)

    rgb_to_intensity_color = FloatVectorProperty(
            name='RGB To Intensity Color', size=3, subtype='COLOR', default=(1.0,1.0,1.0), min=0.0, max=1.0)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            description = 'Normal map type of this texture',
            items = normal_map_type_items,
            default = 'BUMP_MAP')

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        #return hasattr(context, 'group_node') and context.group_node
        return get_active_texture_layers_node()

    def invoke(self, context, event):
        obj = context.object
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None
        if channel and channel.type == 'RGB':
            self.rgb_to_intensity_color = (1.0, 0.0, 1.0)

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
        node = get_active_texture_layers_node()
        tl = node.node_tree.tl
        obj = context.object

        channel = tl.channels[int(self.channel_idx)] if self.channel_idx != '-1' else None

        self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        
        row = self.layout.row()

        col = row.column()
        col.label('Vector:')
        col.label('Channel:')
        if channel and channel.type == 'NORMAL':
            col.label('Type:')

        if self.add_rgb_to_intensity:
            col.label('')
            col.label('RGB2I Color:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_textures", text='', icon='GROUP_UVS')

        #col.label('')
        rrow = col.row(align=True)
        rrow.prop(self, 'channel_idx', text='')
        if channel:
            if channel.type == 'NORMAL':
                rrow.prop(self, 'normal_blend', text='')
                col.prop(self, 'normal_map_type', text='')
            else: 
                rrow.prop(self, 'blend_type', text='')

        col.prop(self, 'add_rgb_to_intensity', text='RGB To Intensity')

        if self.add_rgb_to_intensity:
            col.prop(self, 'rgb_to_intensity_color', text='')

    def execute(self, context):
        node = get_active_texture_layers_node()

        if self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}

        node.node_tree.tl.halt_update = True

        image = bpy.data.images.get(self.image_name)
        add_new_texture(image.name, 'IMAGE', int(self.channel_idx), self.blend_type, 
                self.normal_blend, self.normal_map_type, self.texcoord_type, self.uv_map, 
                image, self.add_rgb_to_intensity, self.rgb_to_intensity_color)

        node.node_tree.tl.halt_update = False

        # Reconnect and rearrange nodes
        reconnect_tl_tex_nodes(node.node_tree)
        rearrange_tl_nodes(node.node_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

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
        group_node = get_active_texture_layers_node()
        return group_node and len(group_node.node_tree.tl.textures) > 0

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tl = group_tree.tl

        num_tex = len(tl.textures)
        tex_idx = tl.active_texture_index
        tex = tl.textures[tex_idx]
        
        # Move image slot
        if self.direction == 'UP' and tex_idx > 0:
            swap_idx = tex_idx-1
        elif self.direction == 'DOWN' and tex_idx < num_tex-1:
            swap_idx = tex_idx+1
        else:
            return {'CANCELLED'}

        swap_tex = tl.textures[swap_idx]

        # Swap texture
        tl.textures.move(tex_idx, swap_idx)
        tl.active_texture_index = swap_idx

        # Repoint channel texture index
        for ch in tl.textures[tex_idx].channels:
            ch.texture_index = tex_idx

        for ch in tl.textures[swap_idx].channels:
            ch.texture_index = swap_idx

        # Refresh texture channel blend nodes
        reconnect_tl_tex_nodes(group_tree)
        rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        return {'FINISHED'}

class YRemoveTextureLayer(bpy.types.Operator):
    bl_idname = "node.y_remove_texture_layer"
    bl_label = "Remove Texture Layer"
    bl_description = "New Texture Layer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        group_node = get_active_texture_layers_node()
        return context.object and group_node and len(group_node.node_tree.tl.textures) > 0

    def invoke(self, context, event):
        obj = context.object
        if obj.mode != 'OBJECT':
            return context.window_manager.invoke_props_dialog(self, width=400)
        return self.execute(context)

    def draw(self, context):
        obj = context.object
        if obj.mode != 'OBJECT':
            self.layout.label('You cannot UNDO this operation under this mode, are you sure?', icon='ERROR')

    def execute(self, context):
        node = get_active_texture_layers_node()
        group_tree = node.node_tree
        nodes = group_tree.nodes
        tl = group_tree.tl

        tex = tl.textures[tl.active_texture_index]

        # Remove node group and tex tree
        nodes.remove(nodes.get(tex.group_node))
        bpy.data.node_groups.remove(tex.tree)

        # Delete the texture
        tl.textures.remove(tl.active_texture_index)

        # Set new active index
        if (tl.active_texture_index == len(tl.textures) and
            tl.active_texture_index > 0
            ):
            tl.active_texture_index -= 1
        else:
            # Force update the index to refesh paint image
            tl.active_texture_index = tl.active_texture_index

        # Repoint channel texture index
        for i in range(tl.active_texture_index, len(tl.textures)):
            for ch in tl.textures[i].channels:
                ch.texture_index = i

        # Refresh texture channel blend nodes
        reconnect_tl_tex_nodes(group_tree)
        rearrange_tl_nodes(group_tree)

        # Update UI
        context.window_manager.tlui.need_update = True

        # Refresh normal map
        tl.refresh_tree = True

        return {'FINISHED'}

def update_channel_enable(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]
    blend = tex.tree.nodes.get(self.blend)

    if tex.enable and self.enable:
        blend.mute = False
    else: blend.mute = True

def update_channel_texture_index(self, context):
    for mod in self.modifiers:
        mod.texture_index = self.texture_index

def update_channel_channel_index(self, context):
    for mod in self.modifiers:
        mod.channel_index = self.channel_index

def update_normal_map_type(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]
    nodes = tex.tree.nodes

    # Normal nodes
    normal = nodes.get(self.normal)

    # Bump nodes
    bump_base = nodes.get(self.bump_base)
    bump = nodes.get(self.bump)
    intensity_multiplier = nodes.get(self.intensity_multiplier)

    # Fine bump nodes
    neighbor_uv = nodes.get(self.neighbor_uv)
    fine_bump = nodes.get(self.fine_bump)

    # Get fine bump sources
    sources = []
    mod_groups = []
    bump_bases = []
    neighbor_directions = ['n', 's', 'e', 'w']
    for d in neighbor_directions:
        s = nodes.get(getattr(self, 'source_' + d))
        m = nodes.get(getattr(self, 'mod_' + d))
        b = nodes.get(getattr(self, 'bump_base_' + d))
        sources.append(s)
        mod_groups.append(m)
        bump_bases.append(b)

    # Common nodes
    normal_flip = nodes.get(self.normal_flip)

    # Bump base is available on standard and fine bump
    if self.normal_map_type in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
        if not bump_base:
            bump_base = nodes.new('ShaderNodeMixRGB')
            bump_base.label = 'Bump Base'
            val = self.bump_base_value
            bump_base.inputs[1].default_value = (val, val, val, 1.0)
            self.bump_base = bump_base.name
        if not intensity_multiplier:
            intensity_multiplier = nodes.new('ShaderNodeMath')
            intensity_multiplier.label = 'Intensity Multiplier'
            intensity_multiplier.inputs[1].default_value = self.intensity_multiplier_value
            intensity_multiplier.use_clamp = True
            intensity_multiplier.operation = 'MULTIPLY'
            self.intensity_multiplier = intensity_multiplier.name

    if self.normal_map_type == 'NORMAL_MAP':
        if not normal:
            normal = nodes.new('ShaderNodeNormalMap')
            normal.uv_map = tex.uv_name
            self.normal = normal.name

    elif self.normal_map_type == 'BUMP_MAP':

        if not bump:
            bump = nodes.new('ShaderNodeBump')
            bump.inputs[1].default_value = self.bump_distance
            self.bump = bump.name

    elif self.normal_map_type == 'FINE_BUMP_MAP':

        # Make sure to enable source tree and modifier tree
        enable_tex_source_tree(tex)
        Modifier.enable_modifiers_tree(self)

        # Get the original source
        source = tex.source_tree.nodes.get(tex.source)

        if not neighbor_uv:
            neighbor_uv = nodes.new('ShaderNodeGroup')
            neighbor_uv.node_tree = lib.get_node_tree_lib(lib.NEIGHBOR_UV)
            neighbor_uv.label = 'Neighbor UV'
            self.neighbor_uv = neighbor_uv.name

        if tex.type == 'IMAGE' and source.image:
            neighbor_uv.inputs[1].default_value = source.image.size[0]
            neighbor_uv.inputs[2].default_value = source.image.size[1]

        if not fine_bump:
            fine_bump = nodes.new('ShaderNodeGroup')
            fine_bump.node_tree = lib.get_node_tree_lib(lib.FINE_BUMP)
            fine_bump.inputs[0].default_value = self.fine_bump_scale
            fine_bump.label = 'Fine Bump'
            self.fine_bump = fine_bump.name

        for i, s in enumerate(sources):
            if not s:
                #s = nodes.new(source.bl_idname)
                s = nodes.new('ShaderNodeGroup')
                s.node_tree = tex.source_tree
                s.label = neighbor_directions[i]
                setattr(self, 'source_' + neighbor_directions[i], s.name)
                s.hide = True

        for i, m in enumerate(mod_groups):
            if not m:
                m = nodes.new('ShaderNodeGroup')
                m.node_tree = self.mod_tree
                m.label = 'mod ' + neighbor_directions[i]
                setattr(self, 'mod_' + neighbor_directions[i], m.name)
                m.hide = True

        for i, b in enumerate(bump_bases):
            if not b:
                b = nodes.new('ShaderNodeMixRGB')
                copy_node_props(bump_base, b, ['parent'])
                b.label = 'bump base ' + neighbor_directions[i]
                setattr(self, 'bump_base_' + neighbor_directions[i], b.name)
                b.hide = True

    # Remove bump nodes
    if self.normal_map_type != 'BUMP_MAP':
        if bump: 
            nodes.remove(bump)
            self.bump = ''

    # Remove normal nodes
    if self.normal_map_type != 'NORMAL_MAP':
        if normal: 
            nodes.remove(normal)
            self.normal = ''

    # Remove fine bump nodes
    if self.normal_map_type != 'FINE_BUMP_MAP':
        if neighbor_uv:
            nodes.remove(neighbor_uv)
            self.neighbor_uv = ''
        
        if fine_bump:
            nodes.remove(fine_bump)
            self.fine_bump = ''

        for i, s in enumerate(sources):
            if s:
                nodes.remove(s)
                setattr(self, 'source_' + neighbor_directions[i], '')

        for i, m in enumerate(mod_groups):
            if m:
                nodes.remove(m)
                setattr(self, 'mod_' + neighbor_directions[i], '')

        for i, b in enumerate(bump_bases):
            if b:
                nodes.remove(b)
                setattr(self, 'bump_base_' + neighbor_directions[i], '')

    # Remove bump base
    if self.normal_map_type not in {'BUMP_MAP', 'FINE_BUMP_MAP'}:
        if bump_base: 
            nodes.remove(bump_base)
            self.bump_base = ''
        if intensity_multiplier: 
            nodes.remove(intensity_multiplier)
            self.intensity_multiplier = ''

    # Try to remove source tree
    if self.normal_map_type in {'NORMAL_MAP', 'BUMP_MAP'}:
        disable_tex_source_tree(tex)
        Modifier.disable_modifiers_tree(self)

    # Create normal flip node
    if not normal_flip:
        normal_flip = nodes.new('ShaderNodeGroup')
        normal_flip.node_tree = lib.get_node_tree_lib(lib.FLIP_BACKFACE_NORMAL)
        normal_flip.label = 'Flip Backface Normal'
        self.normal_flip = normal_flip.name

    reconnect_tex_nodes(tex, self.channel_index)
    rearrange_tex_nodes(tex)

def update_blend_type_(root_ch, tex, ch):
    need_reconnect = False

    nodes = tex.tree.nodes
    blend = nodes.get(ch.blend)

    # Check blend type
    if blend:
        if root_ch.type == 'RGB':
            if ((root_ch.alpha and ch.blend_type == 'MIX' and blend.bl_idname == 'ShaderNodeMixRGB') or
                (not root_ch.alpha and blend.bl_idname == 'ShaderNodeGroup') or
                (ch.blend_type != 'MIX' and blend.bl_idname == 'ShaderNodeGroup')):
                nodes.remove(blend)
                blend = None
                need_reconnect = True
        elif root_ch.type == 'NORMAL':
            if ((ch.normal_blend == 'MIX' and blend.bl_idname == 'ShaderNodeGroup') or
                (ch.normal_blend == 'OVERLAY' and blend.bl_idname == 'ShaderNodeMixRGB')):
                nodes.remove(blend)
                blend = None
                need_reconnect = True

    # Create blend node if its missing
    if not blend:
        if root_ch.type == 'RGB':
            #if ch.blend_type == 'MIX':
            if root_ch.alpha and ch.blend_type == 'MIX':
                blend = nodes.new('ShaderNodeGroup')
                blend.node_tree = lib.get_node_tree_lib(lib.STRAIGHT_OVER)
            else:
                blend = nodes.new('ShaderNodeMixRGB')
                blend.blend_type = ch.blend_type

        elif root_ch.type == 'NORMAL':
            if ch.normal_blend == 'OVERLAY':
                blend = nodes.new('ShaderNodeGroup')
                blend.node_tree = lib.get_node_tree_lib(lib.OVERLAY_NORMAL)
            else:
                blend = nodes.new('ShaderNodeMixRGB')

        else:
            blend = nodes.new('ShaderNodeMixRGB')
            blend.blend_type = ch.blend_type

        blend.label = 'Blend'
        ch.blend = blend.name

        # Blend mute
        if tex.enable and ch.enable:
            blend.mute = False
        else: blend.mute = True

    # Update blend mix
    if root_ch.type != 'NORMAL' and blend.bl_idname == 'ShaderNodeMixRGB' and blend.blend_type != ch.blend_type:
        blend.blend_type = ch.blend_type

    # Check alpha tex input output connection
    start = tex.tree.nodes.get(tex.start)
    if (root_ch.type == 'RGB' and root_ch.alpha and ch.blend_type != 'MIX' and 
        len(start.outputs[root_ch.io_index+1].links) == 0):
        need_reconnect = True

    return need_reconnect

def update_blend_type(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]
    root_ch = tl.channels[self.channel_index]
    if update_blend_type_(root_ch, tex, self):
        reconnect_tex_nodes(tex, self.channel_index)
        rearrange_tex_nodes(tex)

def update_flip_backface_normal(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]

    normal_flip = tex.tree.nodes.get(self.normal_flip)
    normal_flip.mute = self.invert_backface_normal

def update_bump_base_value(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]

    bump_base = tex.tree.nodes.get(self.bump_base)
    val = self.bump_base_value
    bump_base.inputs[1].default_value = (val, val, val, 1.0)

    neighbor_directions = ['n', 's', 'e', 'w']
    for d in neighbor_directions:
        b = tex.tree.nodes.get(getattr(self, 'bump_base_' + d))
        if b: b.inputs[1].default_value = (val, val, val, 1.0)

def update_bump_distance(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]

    bump = tex.tree.nodes.get(self.bump)
    if bump: bump.inputs[1].default_value = self.bump_distance

def update_fine_bump_distance(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]

    fine_bump = tex.tree.nodes.get(self.fine_bump)
    if fine_bump: fine_bump.inputs[0].default_value = self.fine_bump_scale

def update_intensity_multiplier(self, context):
    tl = self.id_data.tl
    tex = tl.textures[self.texture_index]

    intensity_multiplier = tex.tree.nodes.get(self.intensity_multiplier)
    if intensity_multiplier: intensity_multiplier.inputs[1].default_value = self.intensity_multiplier_value

def update_tex_input(self, context):
    tl = self.id_data.tl

    m = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    if not m: return
    tex = tl.textures[int(m.group(1))]
    root_ch = tl.channels[int(m.group(2))]

    if tex.type == 'IMAGE': return

    linear = tex.tree.nodes.get(self.linear)
    if self.tex_input == 'RGB_SRGB' and not linear:
        if root_ch.type == 'VALUE':
            linear = tex.tree.nodes.new('ShaderNodeMath')
            linear.operation = 'POWER'
        elif root_ch.type == 'RGB':
            linear = tex.tree.nodes.new('ShaderNodeGamma')
        linear.label = 'Linear'
        linear.inputs[1].default_value = 1.0 / GAMMA
        self.linear = linear.name

    if self.tex_input != 'RGB_SRGB' and linear:
        tex.tree.nodes.remove(linear)
        self.linear = ''

    reconnect_tex_nodes(tex)
    rearrange_tex_nodes(tex)

def update_uv_name(self, context):
    group_tree = self.id_data
    tl = group_tree.tl
    tex = self
    if not tex.tree: return

    nodes = tex.tree.nodes

    uv_map = nodes.get(tex.uv_map)
    if uv_map: uv_map.uv_map = tex.uv_name

    tangent = nodes.get(tex.tangent)
    if tangent: tangent.uv_map = tex.uv_name

    bitangent = nodes.get(tex.bitangent)
    if bitangent: bitangent.uv_map = tex.uv_name

    for ch in tex.channels:
        normal = nodes.get(ch.normal)
        if normal: normal.uv_map = tex.uv_name

def update_texcoord_type(self, context):
    tree = self.tree
    nodes = tree.nodes
    links = tree.links

    source = nodes.get(self.source)
    texcoord = nodes.get(self.texcoord)
    uv_map = nodes.get(self.uv_map)

    if self.texcoord_type == 'UV':
        links.new(uv_map.outputs[0], source.inputs[0])
    else:
        links.new(texcoord.outputs[self.texcoord_type], source.inputs[0])

def update_texture_enable(self, context):
    group_tree = self.id_data
    tex = self

    for ch in tex.channels:
        blend = tex.tree.nodes.get(ch.blend)
        if tex.enable and ch.enable:
            blend.mute = False
        else: blend.mute = True

class YLayerChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_channel_enable)

    tex_input = EnumProperty(
            name = 'Input from Texture',
            #items = (('RGB', 'Color', ''),
            #         ('ALPHA', 'Alpha / Factor', '')),
            #default = 'RGB',
            items = tex_input_items,
            update = update_tex_input)

    texture_index = IntProperty(default=0, update=update_channel_texture_index)
    channel_index = IntProperty(default=0, update=update_channel_channel_index)

    #color_space = EnumProperty(
    #        name = 'Input Color Space',
    #        items = (('LINEAR', 'Linear', ''),
    #                 ('SRGB', 'sRGB', '')),
    #        default = 'LINEAR',
    #        update = update_tex_channel_color_space)

    normal_map_type = EnumProperty(
            name = 'Normal Map Type',
            items = normal_map_type_items,
            default = 'BUMP_MAP',
            update = update_normal_map_type)

    blend_type = EnumProperty(
        name = 'Blend',
        #items = vector_and_blend_type_items)
        items = blend_type_items,
        default = 'MIX',
        update = update_blend_type)

    normal_blend = EnumProperty(
            name = 'Normal Blend Type',
            items = normal_blend_items,
            default = 'MIX',
            #update = update_vector_blend)
            update = update_blend_type)

    pipeline_frame = StringProperty(default='')

    # Modifiers
    modifiers = CollectionProperty(type=Modifier.YTextureModifier)

    # For some occasion, modifiers are stored in a tree
    #is_mod_tree = BoolProperty(default=False, update=Modifier.update_mod_tree)
    mod_group = StringProperty(default='')
    mod_tree = PointerProperty(type=bpy.types.ShaderNodeTree)

    # Blur
    enable_blur = BoolProperty(default=False, update=Blur.update_tex_channel_blur)
    blur = PointerProperty(type=Blur.YTextureBlur)

    # For UI
    expand_bump_settings = BoolProperty(default=False)
    expand_content = BoolProperty(default=False)

    invert_backface_normal = BoolProperty(default=False, update=update_flip_backface_normal)

    # Node names
    linear = StringProperty(default='')
    blend = StringProperty(default='')
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
    normal_flip = StringProperty(default='')

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

    # Fine bump related
    neighbor_uv = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')

    mod_n = StringProperty(default='')
    mod_s = StringProperty(default='')
    mod_e = StringProperty(default='')
    mod_w = StringProperty(default='')

    bump_base_n = StringProperty(default='')
    bump_base_s = StringProperty(default='')
    bump_base_e = StringProperty(default='')
    bump_base_w = StringProperty(default='')

    fine_bump = StringProperty(default='')

    fine_bump_scale = FloatProperty(
            name='Bump Scale', 
            description= 'Scale of bump', 
            default=4.0, min=-100.0, max=100.0,
            update=update_fine_bump_distance)

    intensity_multiplier_value = FloatProperty(
            name = 'Intensity Multiplier',
            description = 'Intensity Multiplier (can be useful for sharper normal blending transition)',
            default=1.0, min=1.0, max=100.0, 
            update=update_intensity_multiplier)

    intensity_multiplier = StringProperty(default='')

    #modifier_frame = StringProperty(default='')

class YTextureLayer(bpy.types.PropertyGroup):
    name = StringProperty(default='')
    enable = BoolProperty(default=True, update=update_texture_enable)
    channels = CollectionProperty(type=YLayerChannel)

    group_node = StringProperty(default='')
    tree = PointerProperty(type=bpy.types.ShaderNodeTree)

    start = StringProperty(default='')
    end = StringProperty(default='')

    type = EnumProperty(
            name = 'Texture Type',
            items = texture_type_items,
            default = 'IMAGE')

    texcoord_type = EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_texcoord_type)

    # To detect change of texture image
    image_name = StringProperty(default='')

    uv_name = StringProperty(default='', update=update_uv_name)

    # Sources
    source = StringProperty(default='')
    source_tree = PointerProperty(type=bpy.types.ShaderNodeTree)
    source_group = StringProperty(default='')

    # Node names
    #linear = StringProperty(default='')
    solid_alpha = StringProperty(default='')
    texcoord = StringProperty(default='')
    uv_map = StringProperty(default='')
    tangent = StringProperty(default='')
    bitangent = StringProperty(default='')
    geometry = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)

