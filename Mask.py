import bpy, re, time
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import lib, Modifier, transition
from .common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *

def add_new_mask(tex, name, mask_type, texcoord_type, uv_name, image = None, vcol = None):
    tl = tex.id_data.tl
    tl.halt_update = True

    tree = get_tree(tex)
    nodes = tree.nodes

    mask = tex.masks.add()
    mask.name = name
    mask.type = mask_type
    mask.texcoord_type = texcoord_type

    source = new_node(tree, mask, 'source', texture_node_bl_idnames[mask_type], 'Mask Source')
    if image:
        source.image = image
        source.color_space = 'NONE'
    elif vcol:
        source.attribute_name = vcol.name

    if mask_type != 'VCOL':
        uv_map = new_node(tree, mask, 'uv_map', 'ShaderNodeUVMap', 'Mask UV Map')
        uv_map.uv_map = uv_name
        mask.uv_name = uv_name

    for i, root_ch in enumerate(tl.channels):
        ch = tex.channels[i]
        c = mask.channels.add()

    # Check mask multiplies
    check_mask_multiply_nodes(tex, tree)

    # Check mask source tree
    check_mask_source_tree(tex)

    tl.halt_update = False

    return mask

def remove_mask_channel_nodes(tree, c):
    remove_node(tree, c, 'multiply')
    remove_node(tree, c, 'multiply_n')
    remove_node(tree, c, 'multiply_s')
    remove_node(tree, c, 'multiply_e')
    remove_node(tree, c, 'multiply_w')

def remove_mask_channel(tree, tex, ch_index):

    # Remove mask nodes
    for mask in tex.masks:

        # Get channels
        c = mask.channels[ch_index]
        ch = tex.channels[ch_index]

        # Remove mask channel nodes first
        remove_mask_channel_nodes(tree, c)

    # Remove the mask itself
    for mask in tex.masks:
        mask.channels.remove(ch_index)

def remove_mask(tex, mask, obj):

    tree = get_tree(tex)

    disable_mask_source_tree(tex, mask)

    remove_node(tree, mask, 'source', obj=obj)
    remove_node(tree, mask, 'uv_map')

    # Remove mask channel nodes
    for c in mask.channels:
        remove_mask_channel_nodes(tree, c)

    # Remove mask
    for i, m in enumerate(tex.masks):
        if m == mask:
            tex.masks.remove(i)
            break

class YNewLayerMask(bpy.types.Operator):
    bl_idname = "node.y_new_layer_mask"
    bl_label = "New Layer Mask"
    bl_description = "New Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    name = StringProperty(default='')

    type = EnumProperty(
            name = 'Mask Type',
            items = mask_type_items,
            default = 'IMAGE')

    width = IntProperty(name='Width', default = 1024, min=1, max=16384)
    height = IntProperty(name='Height', default = 1024, min=1, max=16384)

    color_option = EnumProperty(
            name = 'Color Option',
            description = 'Color Option',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='WHITE')

    hdr = BoolProperty(name='32 bit Float', default=False)

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_name = StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):

        # HACK: For some reason, checking context.texture on poll will cause problem
        # This method below is to get around that
        self.auto_cancel = False
        if not hasattr(context, 'texture'):
            self.auto_cancel = True
            return self.execute(context)

        obj = context.object
        self.texture = context.texture
        tex = context.texture

        surname = '(' + tex.name + ')'
        if self.type == 'IMAGE':
            #name = 'Image'
            name = 'Mask'
            items = bpy.data.images
            self.name = get_unique_name(name, items, surname)
        elif self.type == 'VCOL' and obj.type == 'MESH':
            name = 'Mask VCol'
            items = obj.data.vertex_colors
            self.name = get_unique_name(name, items, surname)
        else:
            #name += ' ' + [i[1] for i in mask_type_items if i[0] == self.type][0]
            name = 'Mask ' + [i[1] for i in mask_type_items if i[0] == self.type][0]
            items = tex.masks
            self.name = get_unique_name(name, items)
        #name = 'Mask ' + name #+ ' ' + surname

        if obj.type != 'MESH':
            self.texcoord_type = 'Generated'
        elif len(obj.data.uv_layers) > 0:
            # Use active uv layer name by default
            self.uv_name = obj.data.uv_layers.active.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        if hasattr(bpy.utils, 'previews'): # Blender 2.7 only
            row = self.layout.split(percentage=0.4)
        else: row = self.layout.split(factor=0.4)
        col = row.column(align=False)
        col.label(text='Name:')
        if self.type == 'IMAGE':
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type in {'VCOL', 'IMAGE'}:
            col.label(text='Color:')

        if self.type == 'IMAGE':
            col.label(text='')

        if self.type != 'VCOL':
            col.label(text='Vector:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'IMAGE':
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type in {'VCOL', 'IMAGE'}:
            col.prop(self, 'color_option', text='')

        if self.type == 'IMAGE':
            col.prop(self, 'hdr')

        if self.type != 'VCOL':
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                crow.prop_search(self, "uv_name", obj.data, "uv_layers", text='', icon='GROUP_UVS')

    def execute(self, context):
        if self.auto_cancel: return {'CANCELLED'}

        obj = context.object
        tlui = context.window_manager.tlui
        tex = self.texture

        # Check if object is not a mesh
        if self.type == 'VCOL' and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color mask only works with mesh object!")
            return {'CANCELLED'}

        # Check if texture with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in obj.data.vertex_colors if i.name == self.name]
        else: same_name = [m for m in tex.masks if m.name == self.name]
        if same_name:
            if self.type == 'IMAGE':
                self.report({'ERROR'}, "Image named '" + self.name +"' is already available!")
            elif self.type == 'VCOL':
                self.report({'ERROR'}, "Vertex Color named '" + self.name +"' is already available!")
            else: self.report({'ERROR'}, "Mask named '" + self.name +"' is already available!")
            return {'CANCELLED'}
        
        alpha = False
        img = None
        vcol = None

        # New image
        if self.type == 'IMAGE':
            img = bpy.data.images.new(name=self.name, 
                    width=self.width, height=self.height, alpha=alpha, float_buffer=self.hdr)
            if self.color_option == 'WHITE':
                img.generated_color = (1,1,1,1)
            elif self.color_option == 'BLACK':
                img.generated_color = (0,0,0,1)
            img.use_alpha = False

        # New vertex color
        elif self.type == 'VCOL':
            vcol = obj.data.vertex_colors.new(name=self.name)
            if self.color_option == 'WHITE':
                set_obj_vertex_colors(obj, vcol, (1.0, 1.0, 1.0))
            elif self.color_option == 'BLACK':
                set_obj_vertex_colors(obj, vcol, (0.0, 0.0, 0.0))

        # Add new mask
        mask = add_new_mask(tex, self.name, self.type, self.texcoord_type, self.uv_name, img, vcol)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'}:
            mask.active_edit = True

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        tlui.tex_ui.expand_masks = True
        tlui.need_update = True

        return {'FINISHED'}

class YOpenImageAsMask(bpy.types.Operator, ImportHelper):
    """Open Image as Mask"""
    bl_idname = "node.y_open_image_as_mask"
    bl_label = "Open Image as Mask"
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

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        obj = context.object
        self.texture = context.texture

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            self.uv_map = obj.data.uv_layers.active.name

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')

        self.layout.prop(self, 'relative')

    def execute(self, context):
        T = time.time()
        if not hasattr(self, 'texture'): return {'CANCELLED'}

        tex = self.texture
        tl = tex.id_data.tl
        wm = context.window_manager
        tlui = wm.tlui
        obj = context.object

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            # Add new mask
            mask = add_new_mask(tex, image.name, 'IMAGE', self.texcoord_type, self.uv_map, image, None)

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        # Update UI
        wm.tlui.need_update = True
        print('INFO: Image(s) is opened as mask(s) at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.tltimer.time = str(time.time())

        return {'FINISHED'}

class YOpenAvailableDataAsMask(bpy.types.Operator):
    bl_idname = "node.y_open_available_data_as_mask"
    bl_label = "Open available data as Layer Mask"
    bl_description = "Open available data as Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    type = EnumProperty(
            name = 'Layer Type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    texcoord_type = EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map = StringProperty(default='')

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name = StringProperty(name="Vertex Color")
    vcol_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        obj = context.object
        self.texture = context.texture

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            self.uv_map = obj.data.uv_layers.active.name

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            for img in imgs:
                self.image_coll.add().name = img.name
        elif self.type == 'VCOL':
            self.vcol_coll.clear()
            vcols = obj.data.vertex_colors
            for vcol in vcols:
                self.vcol_coll.add().name = vcol.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        if self.type == 'IMAGE':
            self.layout.prop_search(self, "image_name", self, "image_coll", icon='IMAGE_DATA')
        elif self.type == 'VCOL':
            self.layout.prop_search(self, "vcol_name", self, "vcol_coll", icon='GROUP_VCOL')

        row = self.layout.row()

        col = row.column()
        if self.type == 'IMAGE':
            col.label(text='Vector:')

        col = row.column()

        if self.type == 'IMAGE':
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')

    def execute(self, context):
        if not hasattr(self, 'texture'): return {'CANCELLED'}

        tex = self.texture
        tl = tex.id_data.tl
        tlui = context.window_manager.tlui
        obj = context.object

        if self.type == 'IMAGE' and self.image_name == '':
            self.report({'ERROR'}, "No image selected!")
            return {'CANCELLED'}
        elif self.type == 'VCOL' and self.vcol_name == '':
            self.report({'ERROR'}, "No vertex color selected!")
            return {'CANCELLED'}

        image = None
        vcol = None
        if self.type == 'IMAGE':
            image = bpy.data.images.get(self.image_name)
            name = image.name
        elif self.type == 'VCOL':
            vcol = obj.data.vertex_colors.get(self.vcol_name)
            name = vcol.name

        # Add new mask
        mask = add_new_mask(tex, name, self.type, self.texcoord_type, self.uv_map, image, vcol)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'}:
            mask.active_edit = True

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        tlui.tex_ui.expand_masks = True
        tlui.need_update = True

        return {'FINISHED'}

class YMoveLayerMask(bpy.types.Operator):
    bl_idname = "node.y_move_layer_mask"
    bl_label = "Move Layer Mask"
    bl_description = "Move layer mask"
    bl_options = {'REGISTER', 'UNDO'}

    direction = EnumProperty(
            name = 'Direction',
            items = (('UP', 'Up', ''),
                     ('DOWN', 'Down', '')),
            default = 'UP')

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'texture')

    def execute(self, context):
        mask = context.mask
        tex = context.texture

        num_masks = len(tex.masks)
        if num_masks < 2: return {'CANCELLED'}

        m = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        index = int(m.group(2))

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_masks-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Swap masks
        tex.masks.move(index, new_index)

        # Dealing with transition bump
        tree = get_tree(tex)
        check_mask_multiply_nodes(tex, tree)
        check_mask_source_tree(tex) #, bump_ch)

        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

        return {'FINISHED'}

class YRemoveLayerMask(bpy.types.Operator):
    bl_idname = "node.y_remove_layer_mask"
    bl_label = "Remove Layer Mask"
    bl_description = "Remove Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'texture')

    def execute(self, context):
        mask = context.mask
        tex = context.texture
        tree = get_tree(tex)
        obj = context.object
        tl = tex.id_data.tl

        remove_mask(tex, mask, obj)

        reconnect_tex_nodes(tex)
        rearrange_tex_nodes(tex)

        # Seach for active edit mask
        found_active_edit = False
        for m in tex.masks:
            if m.active_edit:
                found_active_edit = True
                break

        # Use texture image as active image if active edit mask not found
        if not found_active_edit:
            #if tex.type == 'IMAGE':
            #    source = get_tex_source(tex, tree)
            #    update_image_editor_image(context, source.image)
            #else:
            #    update_image_editor_image(context, None)
            tl.active_texture_index = tl.active_texture_index

        # Refresh viewport and image editor
        for area in bpy.context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

def update_mask_active_image_edit(self, context):
    if self.halt_update: return

    # Only image mask can be edited
    if self.active_edit and self.type not in {'IMAGE', 'VCOL'}:
        self.halt_update = True
        self.active_edit = False
        self.halt_update = False
        return

    tl = self.id_data.tl

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex_idx = int(match.group(1))
    tex = tl.textures[int(match.group(1))]
    mask_idx = int(match.group(2))

    if self.active_edit: 
        for m in tex.masks:
            if m == self: continue
            m.halt_update = True
            m.active_edit = False
            m.halt_update = False

    # Refresh
    tl.active_texture_index = tex_idx

def update_enable_layer_masks(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    tex = self
    tree = get_tree(tex)
    for mask in tex.masks:
        for ch in mask.channels:
            mute = not ch.enable or not mask.enable or not tex.enable_masks

            multiply = tree.nodes.get(ch.multiply)
            multiply.mute = mute

            for d in neighbor_directions:
                mul = tree.nodes.get(getattr(ch, 'multiply_' + d))
                if mul: mul.mute = mute

def update_layer_mask_channel_enable(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    mask = tex.masks[int(match.group(2))]
    tree = get_tree(tex)

    mute = not self.enable or not mask.enable or not tex.enable_masks

    multiply = tree.nodes.get(self.multiply)
    multiply.mute = mute

    for d in neighbor_directions:
        mul = tree.nodes.get(getattr(self, 'multiply_' + d))
        if mul: mul.mute = mute

def update_layer_mask_enable(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)

    for ch in self.channels:

        mute = not ch.enable or not self.enable or not tex.enable_masks

        multiply = tree.nodes.get(ch.multiply)
        multiply.mute = mute

        for d in neighbor_directions:
            mul = tree.nodes.get(getattr(ch, 'multiply_' + d))
            if mul: mul.mute = mute

    self.active_edit = self.enable and self.type == 'IMAGE'

def update_mask_texcoord_type(self, context):
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]

    reconnect_tex_nodes(tex)

def update_mask_uv_name(self, context):
    obj = context.object
    tl = self.id_data.tl
    if tl.halt_update: return

    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    
    uv_map = tree.nodes.get(self.uv_map)
    uv_map.uv_map = self.uv_name

    # Update uv layer
    if self.active_edit and obj.type == 'MESH':

        if hasattr(obj.data, 'uv_textures'):
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        for i, uv in enumerate(uv_layers):
            if uv.name == self.uv_name:
                if uv_layers.active_index != i:
                    uv_layers.active_index = i
                break

    # Update neighbor uv if mask bump is active
    if set_mask_uv_neighbor(tree, tex, self):
        rearrange_tex_nodes(tex)
        reconnect_tex_nodes(tex)

def update_mask_name(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    src = get_mask_source(self)

    change_texture_name(tl, context.object, src, self, tex.masks)

def update_mask_blend_type(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    mask = self

    for c in mask.channels:
        mul = tree.nodes.get(c.multiply)
        if mul: mul.blend_type = mask.blend_type
        for d in neighbor_directions:
            mul = tree.nodes.get(getattr(c, 'multiply_' + d))
            if mul: mul.blend_type = mask.blend_type

def update_mask_intensity_value(self, context):

    tl = self.id_data.tl
    match = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    tex = tl.textures[int(match.group(1))]
    tree = get_tree(tex)
    mask = self

    for c in mask.channels:
        mul = tree.nodes.get(c.multiply)
        if mul: mul.inputs[0].default_value = mask.intensity_value
        for d in neighbor_directions:
            mul = tree.nodes.get(getattr(c, 'multiply_' + d))
            if mul: mul.inputs[0].default_value = mask.intensity_value

class YLayerMaskChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_layer_mask_channel_enable)

    # Multiply between mask channels
    multiply = StringProperty(default='')

    # Bump related
    multiply_n = StringProperty(default='')
    multiply_s = StringProperty(default='')
    multiply_e = StringProperty(default='')
    multiply_w = StringProperty(default='')

    # Flip bump related
    multiply_extra = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)

class YLayerMask(bpy.types.PropertyGroup):

    name = StringProperty(default='', update=update_mask_name)

    halt_update = BoolProperty(default=False)
    
    group_node = StringProperty(default='')

    enable = BoolProperty(
            name='Enable Mask', 
            description = 'Enable mask',
            default=True, update=update_layer_mask_enable)

    active_edit = BoolProperty(
            name='Active image for editing', 
            description='Active image for editing', 
            default=False,
            update=update_mask_active_image_edit)

    #active_vcol_edit = BoolProperty(
    #        name='Active vertex color for editing', 
    #        description='Active vertex color for editing', 
    #        default=False,
    #        update=update_mask_active_vcol_edit)

    type = EnumProperty(
            name = 'Mask Type',
            items = mask_type_items,
            default = 'IMAGE')

    texcoord_type = EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_mask_texcoord_type)

    uv_name = StringProperty(default='', update=update_mask_uv_name)

    blend_type = EnumProperty(
        name = 'Blend',
        items = blend_type_items,
        default = 'MULTIPLY',
        update = update_mask_blend_type)

    intensity_value = FloatProperty(
            name = 'Mask Intensity Factor', 
            description = 'Mask Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update = update_mask_intensity_value)

    channels = CollectionProperty(type=YLayerMaskChannel)

    # Nodes
    source = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')

    uv_map = StringProperty(default='')
    uv_neighbor = StringProperty(default='')

    tangent = StringProperty(default='')
    bitangent = StringProperty(default='')

    # UI related
    expand_content = BoolProperty(default=False)
    expand_channels = BoolProperty(default=False)
    expand_source = BoolProperty(default=False)
    expand_vector = BoolProperty(default=False)

def register():
    bpy.utils.register_class(YNewLayerMask)
    bpy.utils.register_class(YOpenImageAsMask)
    bpy.utils.register_class(YOpenAvailableDataAsMask)
    bpy.utils.register_class(YMoveLayerMask)
    bpy.utils.register_class(YRemoveLayerMask)
    bpy.utils.register_class(YLayerMaskChannel)
    bpy.utils.register_class(YLayerMask)

def unregister():
    bpy.utils.unregister_class(YNewLayerMask)
    bpy.utils.unregister_class(YOpenImageAsMask)
    bpy.utils.unregister_class(YOpenAvailableDataAsMask)
    bpy.utils.unregister_class(YMoveLayerMask)
    bpy.utils.unregister_class(YRemoveLayerMask)
    bpy.utils.unregister_class(YLayerMaskChannel)
    bpy.utils.unregister_class(YLayerMask)
