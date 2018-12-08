import bpy, re, time
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import lib, Modifier, transition, ImageAtlas, MaskModifier
from .common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *

def add_new_mask(layer, name, mask_type, texcoord_type, uv_name, image = None, vcol = None, segment=None):
    yp = layer.id_data.yp
    yp.halt_update = True

    tree = get_tree(layer)
    nodes = tree.nodes

    mask = layer.masks.add()
    mask.name = name
    mask.type = mask_type
    mask.texcoord_type = texcoord_type

    if segment:
        mask.segment_name = segment.name

    source = new_node(tree, mask, 'source', layer_node_bl_idnames[mask_type], 'Mask Source')
    if image:
        source.image = image
        source.color_space = 'NONE'
    elif vcol:
        source.attribute_name = vcol.name

    if mask_type != 'VCOL':
        uv_map = new_node(tree, mask, 'uv_map', 'ShaderNodeUVMap', 'Mask UV Map')
        uv_map.uv_map = uv_name
        mask.uv_name = uv_name

        mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')

        if segment:
            scale_x = segment.width/image.size[0]
            scale_y = segment.height/image.size[1]

            offset_x = scale_x * segment.tile_x
            offset_y = scale_y * segment.tile_y

            if mapping:
                mapping.scale[0] = scale_x
                mapping.scale[1] = scale_y

                mapping.translation[0] = offset_x
                mapping.translation[1] = offset_y

            refresh_temp_uv(bpy.context.object, mask)

    for i, root_ch in enumerate(yp.channels):
        ch = layer.channels[i]
        c = mask.channels.add()

    # Check mask multiplies
    check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    check_mask_source_tree(layer)

    yp.halt_update = False

    return mask

def remove_mask_channel_nodes(tree, c):
    remove_node(tree, c, 'mix')
    remove_node(tree, c, 'mix_n')
    remove_node(tree, c, 'mix_s')
    remove_node(tree, c, 'mix_e')
    remove_node(tree, c, 'mix_w')

def remove_mask_channel(tree, layer, ch_index):

    # Remove mask nodes
    for mask in layer.masks:

        # Get channels
        c = mask.channels[ch_index]
        ch = layer.channels[ch_index]

        # Remove mask channel nodes first
        remove_mask_channel_nodes(tree, c)

    # Remove the mask itself
    for mask in layer.masks:
        mask.channels.remove(ch_index)

def remove_mask(layer, mask, obj):

    tree = get_tree(layer)

    # Dealing with image atlas segments
    if mask.type == 'IMAGE' and mask.segment_name != '':
        src = get_mask_source(mask)
        segment = src.image.yia.segments.get(mask.segment_name)
        segment.unused = True

    disable_mask_source_tree(layer, mask)

    remove_node(tree, mask, 'source', obj=obj)
    remove_node(tree, mask, 'mapping')
    remove_node(tree, mask, 'uv_map')

    # Remove mask modifiers
    for m in mask.modifiers:
        MaskModifier.delete_modifier_nodes(tree, m)

    # Remove mask channel nodes
    for c in mask.channels:
        remove_mask_channel_nodes(tree, c)

    # Remove mask
    for i, m in enumerate(layer.masks):
        if m == mask:
            layer.masks.remove(i)
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
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    use_image_atlas = BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    @classmethod
    def poll(cls, context):
        return True

    def get_to_be_cleared_image_atlas(self, context):
        if self.type == 'IMAGE' and self.use_image_atlas:
            return ImageAtlas.check_need_of_erasing_segments(self.color_option, self.width, self.height, self.hdr)

        return None

    def invoke(self, context, event):

        # HACK: For some reason, checking context.layer on poll will cause problem
        # This method below is to get around that
        self.auto_cancel = False
        if not hasattr(context, 'layer'):
            self.auto_cancel = True
            return self.execute(context)

        obj = context.object
        self.layer = context.layer
        layer = context.layer
        yp = layer.id_data.yp

        surname = '(' + layer.name + ')'
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
            items = layer.masks
            self.name = get_unique_name(name, items)
        #name = 'Mask ' + name #+ ' ' + surname

        if obj.type != 'MESH':
            self.texcoord_type = 'Generated'
        elif len(obj.data.uv_layers) > 0:
            # Use active uv layer name by default
            if obj.data.uv_layers.active.name == TEMP_UV:
                self.uv_name = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_name = obj.data.uv_layers.active.name

            # UV Map collections update
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        if bpy.app.version_string.startswith('2.8'):
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

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
            col.label(text='')

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
                crow.prop_search(self, "uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
            col.prop(self, 'use_image_atlas')

        if self.get_to_be_cleared_image_atlas(context):
            col = self.layout.column(align=True)
            col.label(text='INFO: An unused atlas segment can be used.', icon='ERROR')
            col.label(text='It will take a couple seconds to clear.')

    def execute(self, context):
        if self.auto_cancel: return {'CANCELLED'}

        obj = context.object
        ypui = context.window_manager.ypui
        layer = self.layer
        #ypup = bpy.context.user_preferences.addons[__package__].preferences

        # Check if object is not a mesh
        if self.type == 'VCOL' and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color mask only works with mesh object!")
            return {'CANCELLED'}

        # Clearing unused image atlas segments
        img_atlas = self.get_to_be_cleared_image_atlas(context)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        # Check if layer with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in obj.data.vertex_colors if i.name == self.name]
        else: same_name = [m for m in layer.masks if m.name == self.name]
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
        segment = None

        # New image
        if self.type == 'IMAGE':
            if self.use_image_atlas:
                segment = ImageAtlas.get_set_image_atlas_segment(
                        self.width, self.height, self.color_option, self.hdr) #, ypup.image_atlas_size)
                img = segment.id_data
            else:
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
        mask = add_new_mask(layer, self.name, self.type, self.texcoord_type, self.uv_name, img, vcol, segment)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'}:
            mask.active_edit = True

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        ypui.layer_ui.expand_masks = True
        ypui.need_update = True

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
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    def generate_paths(self):
        return (fn.name for fn in self.files), self.directory

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        obj = context.object
        self.layer = context.layer
        yp = self.layer.id_data.yp

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            #self.uv_map = obj.data.uv_layers.active.name
            if obj.data.uv_layers.active.name == TEMP_UV:
                self.uv_map = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_map = obj.data.uv_layers.active.name

            # UV Map collections update
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

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
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        self.layout.prop(self, 'relative')

    def execute(self, context):
        T = time.time()
        if not hasattr(self, 'layer'): return {'CANCELLED'}

        layer = self.layer
        yp = layer.id_data.yp
        wm = context.window_manager
        ypui = wm.ypui
        obj = context.object

        import_list, directory = self.generate_paths()
        images = tuple(load_image(path, directory) for path in import_list)

        for image in images:
            if self.relative:
                try: image.filepath = bpy.path.relpath(image.filepath)
                except: pass

            # Add new mask
            mask = add_new_mask(layer, image.name, 'IMAGE', self.texcoord_type, self.uv_map, image, None)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        # Update UI
        wm.ypui.need_update = True
        print('INFO: Image(s) is opened as mask(s) at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        wm.yptimer.time = str(time.time())

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
    uv_map_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    image_name = StringProperty(name="Image")
    image_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name = StringProperty(name="Vertex Color")
    vcol_coll = CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        obj = context.object
        self.layer = context.layer
        yp = self.layer.id_data.yp

        if obj.type != 'MESH':
            self.texcoord_type = 'Object'

        # Use active uv layer name by default
        if obj.type == 'MESH' and len(obj.data.uv_layers) > 0:
            #self.uv_map = obj.data.uv_layers.active.name
            if obj.data.uv_layers.active.name == TEMP_UV:
                self.uv_map = yp.layers[yp.active_layer_index].uv_name
            else: self.uv_map = obj.data.uv_layers.active.name

            # UV Map collections update
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            for img in imgs:
                if not img.yia.is_image_atlas:
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
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

    def execute(self, context):
        if not hasattr(self, 'layer'): return {'CANCELLED'}

        layer = self.layer
        yp = layer.id_data.yp
        ypui = context.window_manager.ypui
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
        mask = add_new_mask(layer, name, self.type, self.texcoord_type, self.uv_map, image, vcol)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'}:
            mask.active_edit = True

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        ypui.layer_ui.expand_masks = True
        ypui.need_update = True

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
        return hasattr(context, 'mask') and hasattr(context, 'layer')

    def execute(self, context):
        mask = context.mask
        layer = context.layer

        num_masks = len(layer.masks)
        if num_masks < 2: return {'CANCELLED'}

        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        index = int(m.group(2))

        # Get new index
        if self.direction == 'UP' and index > 0:
            new_index = index-1
        elif self.direction == 'DOWN' and index < num_masks-1:
            new_index = index+1
        else:
            return {'CANCELLED'}

        # Swap masks
        layer.masks.move(index, new_index)

        # Dealing with transition bump
        tree = get_tree(layer)
        check_mask_mix_nodes(layer, tree)
        check_mask_source_tree(layer) #, bump_ch)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        return {'FINISHED'}

class YRemoveLayerMask(bpy.types.Operator):
    bl_idname = "node.y_remove_layer_mask"
    bl_label = "Remove Layer Mask"
    bl_description = "Remove Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'mask') and hasattr(context, 'layer')

    def execute(self, context):
        mask = context.mask
        layer = context.layer
        tree = get_tree(layer)
        obj = context.object
        yp = layer.id_data.yp

        remove_mask(layer, mask, obj)

        reconnect_layer_nodes(layer)
        rearrange_layer_nodes(layer)

        # Seach for active edit mask
        found_active_edit = False
        for m in layer.masks:
            if m.active_edit:
                found_active_edit = True
                break

        # Use layer image as active image if active edit mask not found
        if not found_active_edit:
            #if layer.type == 'IMAGE':
            #    source = get_layer_source(layer, tree)
            #    update_image_editor_image(context, source.image)
            #else:
            #    update_image_editor_image(context, None)
            yp.active_layer_index = yp.active_layer_index

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

    yp = self.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer_idx = int(match.group(1))
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))

    if self.active_edit: 
        for m in layer.masks:
            if m == self: continue
            m.halt_update = True
            m.active_edit = False
            m.halt_update = False

    # Refresh
    yp.active_layer_index = layer_idx

def update_enable_layer_masks(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    layer = self
    tree = get_tree(layer)
    for mask in layer.masks:
        for ch in mask.channels:
            mute = not ch.enable or not mask.enable or not layer.enable_masks

            mix = tree.nodes.get(ch.mix)
            mix.mute = mute

            for d in neighbor_directions:
                mix = tree.nodes.get(getattr(ch, 'mix_' + d))
                if mix: mix.mute = mute

def update_layer_mask_channel_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    tree = get_tree(layer)

    mute = not self.enable or not mask.enable or not layer.enable_masks

    mix = tree.nodes.get(self.mix)
    mix.mute = mute

    for d in neighbor_directions:
        mix = tree.nodes.get(getattr(self, 'mix_' + d))
        if mix: mix.mute = mute

def update_layer_mask_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    for ch in self.channels:

        mute = not ch.enable or not self.enable or not layer.enable_masks

        mix = tree.nodes.get(ch.mix)
        mix.mute = mute

        for d in neighbor_directions:
            mix = tree.nodes.get(getattr(ch, 'mix_' + d))
            if mix: mix.mute = mute

    self.active_edit = self.enable and self.type == 'IMAGE'

def update_mask_texcoord_type(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]

    reconnect_layer_nodes(layer)

def update_mask_uv_name(self, context):
    obj = context.object
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)
    mask = self

    uv_map = tree.nodes.get(mask.uv_map)

    # Cannot use temp uv as standard uv
    if mask.uv_name == TEMP_UV:
        mask.uv_name = uv_map.uv_map
    
    uv_map.uv_map = mask.uv_name

    # Update uv layer
    if mask.active_edit and obj.type == 'MESH':

        if mask.segment_name != '':
            refresh_temp_uv(obj, mask)
        else:

            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            for i, uv in enumerate(uv_layers):
                if uv.name == mask.uv_name:
                    if uv_layers.active_index != i:
                        uv_layers.active_index = i
                    break

    # Update neighbor uv if mask bump is active
    if set_mask_uv_neighbor(tree, layer, self):
        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

def update_mask_name(self, context):

    yp = self.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    src = get_mask_source(self)

    if self.type == 'IMAGE' and self.segment_name != '': return
    change_layer_name(yp, context.object, src, self, layer.masks)

def update_mask_blend_type(self, context):

    yp = self.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)
    mask = self

    for c in mask.channels:
        mix = tree.nodes.get(c.mix)
        if mix: mix.blend_type = mask.blend_type
        for d in neighbor_directions:
            mix = tree.nodes.get(getattr(c, 'mix_' + d))
            if mix: mix.blend_type = mask.blend_type

def update_mask_intensity_value(self, context):

    yp = self.id_data.yp
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)
    mask = self

    for c in mask.channels:
        mix = tree.nodes.get(c.mix)
        if mix: mix.inputs[0].default_value = mask.intensity_value
        for d in neighbor_directions:
            mix = tree.nodes.get(getattr(c, 'mix_' + d))
            if mix: mix.inputs[0].default_value = mask.intensity_value

def update_mask_transform(self, context):
    update_mapping(self)

class YLayerMaskChannel(bpy.types.PropertyGroup):
    enable = BoolProperty(default=True, update=update_layer_mask_channel_enable)

    # Multiply between mask channels
    mix = StringProperty(default='')

    # Bump related
    mix_n = StringProperty(default='')
    mix_s = StringProperty(default='')
    mix_e = StringProperty(default='')
    mix_w = StringProperty(default='')

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

    # Transform
    translation = FloatVectorProperty(
            name='Translation', size=3, precision=3, 
            default=(0.0, 0.0, 0.0),
            update=update_mask_transform
            ) #, step=1)

    rotation = FloatVectorProperty(
            name='Rotation', subtype='AXISANGLE', size=3, precision=3, unit='ROTATION', 
            default=(0.0, 0.0, 0.0),
            update=update_mask_transform
            ) #, step=3)

    scale = FloatVectorProperty(
            name='Scale', size=3, precision=3, 
            default=(1.0, 1.0, 1.0),
            update=update_mask_transform,
            ) #, step=3)

    segment_name = StringProperty(default='')

    channels = CollectionProperty(type=YLayerMaskChannel)

    modifiers = CollectionProperty(type=MaskModifier.YMaskModifier)

    # Nodes
    source = StringProperty(default='')
    source_n = StringProperty(default='')
    source_s = StringProperty(default='')
    source_e = StringProperty(default='')
    source_w = StringProperty(default='')

    uv_map = StringProperty(default='')
    uv_neighbor = StringProperty(default='')
    mapping = StringProperty(default='')

    need_temp_uv_refresh = BoolProperty(default=False)

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
