import bpy, re, time, random
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from bpy_extras.image_utils import load_image  
from . import lib, Modifier, transition, ImageAtlas, MaskModifier, UDIM
from .common import *
from .node_connections import *
from .node_arrangements import *
from .subtree import *
from .input_outputs import *

#def check_object_index_props(entity, source=None):
#    source.inputs[0].default_value = entity.object_index

def add_new_mask(layer, name, mask_type, texcoord_type, uv_name, image = None, vcol = None, segment=None, object_index=0, blend_type='MULTIPLY', hemi_space='WORLD', hemi_use_prev_normal=False, color_id=(1,0,1)):
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

    if mask_type == 'VCOL':
        source = new_node(tree, mask, 'source', get_vcol_bl_idname(), 'Mask Source')
    else: source = new_node(tree, mask, 'source', layer_node_bl_idnames[mask_type], 'Mask Source')
    if image:
        source.image = image
        if hasattr(source, 'color_space'):
            source.color_space = 'NONE'
    elif vcol:
        set_source_vcol_name(source, vcol.name)

    if mask_type == 'HEMI':
        source.node_tree = get_node_tree_lib(lib.HEMI)
        duplicate_lib_node_tree(source)
        mask.hemi_space = hemi_space
        mask.hemi_use_prev_normal = hemi_use_prev_normal

    if mask_type == 'OBJECT_INDEX':
        source.node_tree = get_node_tree_lib(lib.OBJECT_INDEX_EQUAL)
        mask.object_index = object_index
        source.inputs[0].default_value = object_index

    if mask_type == 'COLOR_ID':
        source.node_tree = get_node_tree_lib(lib.COLOR_ID_EQUAL)
        mask.color_id = color_id
        col = (color_id[0], color_id[1], color_id[2], 1.0)
        source.inputs[0].default_value = col

    if mask_type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
        #uv_map = new_node(tree, mask, 'uv_map', 'ShaderNodeUVMap', 'Mask UV Map')
        #uv_map.uv_map = uv_name
        mask.uv_name = uv_name

        mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping', 'Mask Mapping')

        if segment:
            ImageAtlas.set_segment_mapping(mask, segment, image)
            refresh_temp_uv(bpy.context.object, mask)

    for i, root_ch in enumerate(yp.channels):
        ch = layer.channels[i]
        c = mask.channels.add()

    mask.blend_type = blend_type

    # Check mask multiplies
    check_mask_mix_nodes(layer, tree)

    # Check mask source tree
    check_mask_source_tree(layer)

    # Check the need of bump process
    check_layer_bump_process(layer, tree)

    # Check uv maps
    check_uv_nodes(yp)

    # Check layer io
    check_all_layer_channel_io_and_nodes(layer, tree)

    # Check mask linear
    check_mask_image_linear_node(mask)

    yp.halt_update = False

    return mask

def remove_mask_channel_nodes(tree, c):
    remove_node(tree, c, 'mix')
    remove_node(tree, c, 'mix_n')
    remove_node(tree, c, 'mix_s')
    remove_node(tree, c, 'mix_e')
    remove_node(tree, c, 'mix_w')
    remove_node(tree, c, 'mix_pure')
    remove_node(tree, c, 'mix_remains')
    remove_node(tree, c, 'mix_normal')
    remove_node(tree, c, 'mix_limit')
    remove_node(tree, c, 'mix_limit_normal')

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
    yp = layer.id_data.yp
    mat = obj.active_material

    # Get mask index
    mask_index = [i for i, m in enumerate(layer.masks) if m == mask][0]

    # Remove mask fcurves first
    remove_entity_fcurves(mask)
    shift_mask_fcurves_up(layer, mask_index)

    # Dealing with image atlas segments
    if mask.type == 'IMAGE':
        src = get_mask_source(mask)
        if src and src.image:
            image = src.image
            if mask.segment_name != '':
                if image.yia.is_image_atlas:
                    segment = image.yia.segments.get(mask.segment_name)
                    segment.unused = True
                elif image.yua.is_udim_atlas:
                    UDIM.remove_udim_atlas_segment_by_name(image, mask.segment_name, yp=yp)

    disable_mask_source_tree(layer, mask)

    remove_node(tree, mask, 'source')
    remove_node(tree, mask, 'blur_vector')
    remove_node(tree, mask, 'mapping')
    remove_node(tree, mask, 'linear')
    remove_node(tree, mask, 'uv_map')

    # Remove mask modifiers
    for m in mask.modifiers:
        MaskModifier.delete_modifier_nodes(tree, m)

    # Remove mask channel nodes
    for c in mask.channels:
        remove_mask_channel_nodes(tree, c)

    # Remove mask
    layer.masks.remove(mask_index)

def get_new_mask_name(obj, layer, mask_type):
    surname = '(' + layer.name + ')'
    if mask_type == 'IMAGE':
        #name = 'Image'
        name = 'Mask'
        name = get_unique_name(name, layer.masks, surname)
        name = get_unique_name(name, bpy.data.images)
        return name
    elif mask_type == 'VCOL' and obj.type == 'MESH':
        name = 'Mask VCol'
        items = get_vertex_colors(obj)
        return get_unique_name(name, items, surname)
    else:
        name = 'Mask ' + [i[1] for i in mask_type_items if i[0] == mask_type][0]
        items = layer.masks
        return get_unique_name(name, items, surname)

def update_new_mask_uv_map(self, context):
    if not UDIM.is_udim_supported(): return
    if self.type != 'IMAGE': 
        self.use_udim = False
        return

    mat = get_active_material()
    objs = get_all_objects_with_same_materials(mat)
    self.use_udim = UDIM.is_uvmap_udim(objs, self.uv_name)

class YNewLayerMask(bpy.types.Operator):
    bl_idname = "node.y_new_layer_mask"
    bl_label = "New Layer Mask"
    bl_description = "New Layer Mask"
    bl_options = {'REGISTER', 'UNDO'}

    name : StringProperty(default='')

    type : EnumProperty(
            name = 'Mask Type',
            items = mask_type_items,
            default = 'IMAGE')

    width : IntProperty(name='Width', default = 1234, min=1, max=16384)
    height : IntProperty(name='Height', default = 1234, min=1, max=16384)
    
    blend_type : EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 'MULTIPLY')

    color_option : EnumProperty(
            name = 'Color Option',
            description = 'Color Option',
            items = (
                ('WHITE', 'White (Full Opacity)', ''),
                ('BLACK', 'Black (Full Transparency)', ''),
                ),
            default='WHITE')

    color_id : FloatVectorProperty(
            name='Color ID', size=3,
            subtype='COLOR',
            default=(1.0, 0.0, 1.0),
            min=0.0, max=1.0,
            )

    hdr : BoolProperty(name='32 bit Float', default=False)

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_name : StringProperty(default='', update=update_new_mask_uv_map)
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    use_udim : BoolProperty(
            name = 'Use UDIM Tiles',
            description='Use UDIM Tiles',
            default=False)

    use_image_atlas : BoolProperty(
            name = 'Use Image Atlas',
            description='Use Image Atlas',
            default=False)

    # For fake lighting
    hemi_space : EnumProperty(
            name = 'Fake Lighting Space',
            description = 'Fake lighting space',
            items = hemi_space_items,
            default='WORLD')

    hemi_use_prev_normal : BoolProperty(
            name = 'Use previous Normal',
            description = 'Take account previous Normal',
            default = True)

    # For object index
    object_index : IntProperty(
            name = 'Object Index',
            description = 'Object Pass Index',
            default = 0,
            min=0)

    vcol_data_type : EnumProperty(
            name = 'Vertex Color Data Type',
            description = 'Vertex color data type',
            items = vcol_data_type_items,
            default='BYTE_COLOR')

    vcol_domain : EnumProperty(
            name = 'Vertex Color Domain',
            description = 'Vertex color domain',
            items = vcol_domain_items,
            default='CORNER')

    @classmethod
    def poll(cls, context):
        return True

    def get_to_be_cleared_image_atlas(self, context, yp):
        if self.type == 'IMAGE' and self.use_image_atlas:
            return ImageAtlas.check_need_of_erasing_segments(yp, self.color_option, self.width, self.height, self.hdr)

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
        ypup = get_user_preferences()

        #surname = '(' + layer.name + ')'
        #if self.type == 'IMAGE':
        #    #name = 'Image'
        #    name = 'Mask'
        #    items = bpy.data.images
        #    self.name = get_unique_name(name, items, surname)
        #elif self.type == 'VCOL' and obj.type == 'MESH':
        #    name = 'Mask VCol'
        #    items = get_vertex_colors(obj)
        #    self.name = get_unique_name(name, items, surname)
        #else:
        #    #name += ' ' + [i[1] for i in mask_type_items if i[0] == self.type][0]
        #    name = 'Mask ' + [i[1] for i in mask_type_items if i[0] == self.type][0]
        #    items = layer.masks
        #    self.name = get_unique_name(name, items, surname)
        ##name = 'Mask ' + name #+ ' ' + surname
        self.name = get_new_mask_name(obj, layer, self.type)

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

        if self.type == 'COLOR_ID':
            # Check if color id already being used
            while True:
                # Use color id tolerance value as lowest value to avoid pure black color
                self.color_id = (random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0), random.uniform(COLORID_TOLERANCE, 1.0))
                if not is_colorid_already_being_used(yp, self.color_id): break

        if obj.type != 'MESH':
            self.texcoord_type = 'Generated'
        elif len(obj.data.uv_layers) > 0:

            self.uv_name = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # The default blend type for mask is multiply
        if len(layer.masks) == 0:
            self.blend_type = 'MULTIPLY'

        return context.window_manager.invoke_props_dialog(self)

    def check(self, context):
        ypup = get_user_preferences()

        # New image cannot use more pixels than the image atlas
        if self.use_image_atlas:
            if self.hdr: max_size = ypup.hdr_image_atlas_size
            else: max_size = ypup.image_atlas_size
            if self.width > max_size: self.width = max_size
            if self.height > max_size: self.height = max_size

        return True

    def draw(self, context):
        obj = context.object
        yp = self.layer.id_data.yp

        if is_greater_than_280():
            row = self.layout.split(factor=0.4)
        else: row = self.layout.split(percentage=0.4)

        col = row.column(align=False)
        col.label(text='Name:')
        if self.type == 'IMAGE':
            col.label(text='Width:')
            col.label(text='Height:')

        if self.type in {'VCOL', 'IMAGE'}:
            col.label(text='Color:')

        if self.type == 'COLOR_ID':
            col.label(text='Color ID:')

        if is_greater_than_320() and self.type == 'VCOL':
            col.label(text='Domain:')
            col.label(text='Data Type:')

        if self.type == 'HEMI':
            col.label(text='Space:')
            col.label(text='')

        if self.type == 'IMAGE':
            col.label(text='')

        if self.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
            col.label(text='Vector:')
            if self.type == 'IMAGE':
                if UDIM.is_udim_supported():
                    col.label(text='')
                col.label(text='')

        if self.type == 'OBJECT_INDEX':
            col.label(text='Object Index')

        if len(self.layer.masks) > 0:
            col.label(text='Blend:')

        col = row.column(align=False)
        col.prop(self, 'name', text='')
        if self.type == 'IMAGE':
            col.prop(self, 'width', text='')
            col.prop(self, 'height', text='')

        if self.type in {'VCOL', 'IMAGE'}:
            col.prop(self, 'color_option', text='')

        if self.type == 'COLOR_ID':
            col.prop(self, 'color_id', text='')

        if self.type == 'HEMI':
            col.prop(self, 'hemi_space', text='')
            col.prop(self, 'hemi_use_prev_normal')

        if is_greater_than_320() and self.type == 'VCOL':
            crow = col.row(align=True)
            crow.prop(self, 'vcol_domain', expand=True)
            crow = col.row(align=True)
            crow.prop(self, 'vcol_data_type', expand=True)

        if self.type == 'IMAGE':
            col.prop(self, 'hdr')

        if self.type not in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID'}:
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                crow.prop_search(self, "uv_name", self, "uv_map_coll", text='', icon='GROUP_UVS')
                if self.type == 'IMAGE':
                    if UDIM.is_udim_supported():
                        col.prop(self, 'use_udim')
                    ccol = col.column()
                    ccol.prop(self, 'use_image_atlas')

        if self.get_to_be_cleared_image_atlas(context, yp):
            col = self.layout.column(align=True)
            col.label(text='INFO: An unused atlas segment can be used.', icon='ERROR')
            col.label(text='It will take a couple seconds to clear.')
        
        if self.type == 'OBJECT_INDEX':
            col.prop(self, 'object_index', text='')

        if len(self.layer.masks) > 0:
            col.prop(self, 'blend_type', text='')

    def execute(self, context):
        if self.auto_cancel: return {'CANCELLED'}

        obj = context.object
        mat = obj.active_material
        ypui = context.window_manager.ypui
        layer = self.layer
        yp = layer.id_data.yp
        #ypup = get_user_preferences()

        # Check if object is not a mesh
        if self.type == 'VCOL' and obj.type != 'MESH':
            self.report({'ERROR'}, "Vertex color mask only works with mesh object!")
            return {'CANCELLED'}

        if not is_greater_than_330() and self.type == 'VCOL' and len(get_vertex_colors(obj)) >= 8:
            self.report({'ERROR'}, "Mesh can only use 8 vertex colors!")
            return {'CANCELLED'}

        # Clearing unused image atlas segments
        img_atlas = self.get_to_be_cleared_image_atlas(context, yp)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        # Check if layer with same name is already available
        if self.type == 'IMAGE':
            same_name = [i for i in bpy.data.images if i.name == self.name]
        elif self.type == 'VCOL':
            same_name = [i for i in get_vertex_colors(obj) if i.name == self.name]
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

            if self.color_option == 'WHITE':
                color = (1,1,1,1)
            elif self.color_option == 'BLACK':
                color = (0,0,0,1)

            if self.use_udim:
                objs = get_all_objects_with_same_materials(mat)
                tilenums = UDIM.get_tile_numbers(objs, self.uv_name)

            if self.use_image_atlas:
                if self.use_udim:
                    segment = UDIM.get_set_udim_atlas_segment(tilenums, self.width, self.height, color, 'Non-Color', self.hdr, yp)
                else:
                    segment = ImageAtlas.get_set_image_atlas_segment(
                            self.width, self.height, self.color_option, self.hdr, yp=yp) #, ypup.image_atlas_size)
                img = segment.id_data
            else:

                if self.use_udim:
                    img = bpy.data.images.new(name=self.name, width=self.width, height=self.height, 
                            alpha=alpha, float_buffer=self.hdr, tiled=True)

                    # Fill tiles
                    for tilenum in tilenums:
                        UDIM.fill_tile(img, tilenum, color, self.width, self.height)
                    UDIM.initial_pack_udim(img, color)

                else:
                    img = bpy.data.images.new(name=self.name, 
                            width=self.width, height=self.height, alpha=alpha, float_buffer=self.hdr)

                img.generated_color = color
                if hasattr(img, 'use_alpha'):
                    img.use_alpha = False

            if img.colorspace_settings.name != 'Non-Color' and not img.is_dirty:
                img.colorspace_settings.name = 'Non-Color'

        # New vertex color
        elif self.type in {'VCOL', 'COLOR_ID'}:

            objs = [obj]
            if mat.users > 1:
                for o in get_scene_objects():
                    if o.type != 'MESH': continue
                    if mat.name in o.data.materials and o not in objs:
                        objs.append(o)

            if self.type == 'VCOL':

                for o in objs:
                    ovcols = get_vertex_colors(o)
                    if self.name not in ovcols:
                        try:
                            vcol = new_vertex_color(o, self.name, self.vcol_data_type, self.vcol_domain)
                            if self.color_option == 'WHITE':
                                set_obj_vertex_colors(o, vcol.name, (1.0, 1.0, 1.0, 1.0))
                            elif self.color_option == 'BLACK':
                                set_obj_vertex_colors(o, vcol.name, (0.0, 0.0, 0.0, 1.0))
                            set_active_vertex_color(o, vcol)
                        except Exception as ex:
                            print(ex)
                            pass

            elif self.type == 'COLOR_ID':
                check_colorid_vcol(objs)

        # Add new mask
        mask = add_new_mask(layer, self.name, self.type, self.texcoord_type, self.uv_name, img, vcol, segment, self.object_index, self.blend_type, 
                self.hemi_space, self.hemi_use_prev_normal, self.color_id)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL', 'COLOR_ID'}:
            mask.active_edit = True

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        rearrange_yp_nodes(layer.id_data)
        reconnect_yp_nodes(layer.id_data)

        ypui.layer_ui.expand_masks = True
        ypui.need_update = True

        return {'FINISHED'}

class YOpenImageAsMask(bpy.types.Operator, ImportHelper):
    """Open Image as Mask"""
    bl_idname = "node.y_open_image_as_mask"
    bl_label = "Open Image as Mask"
    bl_options = {'REGISTER', 'UNDO'}

    # File related
    files : CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'}) 

    # File browser filter
    filter_folder : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_image : BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    display_type : EnumProperty(
            items = (('FILE_DEFAULTDISPLAY', 'Default', ''),
                     ('FILE_SHORTDISLPAY', 'Short List', ''),
                     ('FILE_LONGDISPLAY', 'Long List', ''),
                     ('FILE_IMGDISPLAY', 'Thumbnails', '')),
            default = 'FILE_IMGDISPLAY',
            options={'HIDDEN', 'SKIP_SAVE'})

    relative : BoolProperty(name="Relative Path", default=True, description="Apply relative paths")

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    blend_type : EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 'MULTIPLY')

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

            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        # The default blend type for mask is multiply
        if len(self.layer.masks) == 0:
            self.blend_type = 'MULTIPLY'

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def check(self, context):
        return True

    def draw(self, context):
        obj = context.object

        row = self.layout.row()

        col = row.column()
        col.label(text='Vector:')
        if len(self.layer.masks) > 0:
            col.label(text='Blend:')

        col = row.column()
        crow = col.row(align=True)
        crow.prop(self, 'texcoord_type', text='')
        if obj.type == 'MESH' and self.texcoord_type == 'UV':
            #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
            crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if len(self.layer.masks) > 0:
            col.prop(self, 'blend_type', text='')

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

            if image.colorspace_settings.name != 'Non-Color' and not image.is_dirty:
                image.colorspace_settings.name = 'Non-Color'

            # Add new mask
            mask = add_new_mask(layer, image.name, 'IMAGE', self.texcoord_type, self.uv_map, image, None, blend_type=self.blend_type)

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        rearrange_yp_nodes(layer.id_data)
        reconnect_yp_nodes(layer.id_data)

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

    type : EnumProperty(
            name = 'Layer Type',
            items = (('IMAGE', 'Image', ''),
                ('VCOL', 'Vertex Color', '')),
            default = 'IMAGE')

    texcoord_type : EnumProperty(
            name = 'Texture Coordinate Type',
            items = texcoord_type_items,
            default = 'UV')

    uv_map : StringProperty(default='')
    uv_map_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    image_name : StringProperty(name="Image")
    image_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    vcol_name : StringProperty(name="Vertex Color")
    vcol_coll : CollectionProperty(type=bpy.types.PropertyGroup)

    blend_type : EnumProperty(
        name = 'Blend',
        description = 'Blend type',
        items = mask_blend_type_items,
        default = 'MULTIPLY')

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

            self.uv_map = get_default_uv_name(obj, yp)

            # UV Map collections update
            self.uv_map_coll.clear()
            for uv in obj.data.uv_layers:
                if not uv.name.startswith(TEMP_UV):
                    self.uv_map_coll.add().name = uv.name

        if self.type == 'IMAGE':
            # Update image names
            self.image_coll.clear()
            imgs = bpy.data.images
            baked_channel_images = get_all_baked_channel_images(self.layer.id_data)
            for img in imgs:
                if not img.yia.is_image_atlas and img not in baked_channel_images:
                    self.image_coll.add().name = img.name
        elif self.type == 'VCOL':
            self.vcol_coll.clear()
            for vcol in get_vertex_colors(obj):
                self.vcol_coll.add().name = vcol.name

        # The default blend type for mask is multiply
        if len(self.layer.masks) == 0:
            self.blend_type = 'MULTIPLY'

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
            if len(self.layer.masks) > 0:
                col.label(text='Blend:')

        col = row.column()

        if self.type == 'IMAGE':
            crow = col.row(align=True)
            crow.prop(self, 'texcoord_type', text='')
            if obj.type == 'MESH' and self.texcoord_type == 'UV':
                #crow.prop_search(self, "uv_map", obj.data, "uv_layers", text='', icon='GROUP_UVS')
                crow.prop_search(self, "uv_map", self, "uv_map_coll", text='', icon='GROUP_UVS')

        if len(self.layer.masks) > 0:
            col.prop(self, 'blend_type', text='')

    def execute(self, context):
        if not hasattr(self, 'layer'): return {'CANCELLED'}

        layer = self.layer
        yp = layer.id_data.yp
        ypui = context.window_manager.ypui
        obj = context.object
        mat = obj.active_material

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
            if image.colorspace_settings.name != 'Non-Color' and not image.is_dirty:
                image.colorspace_settings.name = 'Non-Color'
        elif self.type == 'VCOL':
            vcols = get_vertex_colors(obj)
            vcol = vcols.get(self.vcol_name)
            name = vcol.name

            if mat.users > 1:
                for o in get_scene_objects():
                    ovcols = get_vertex_colors(o)
                    if o.type != 'MESH' or o == obj: continue
                    if mat.name in o.data.materials and self.vcol_name not in ovcols:
                        try:
                            if is_greater_than_320():
                                other_v = new_vertex_color(o, self.vcol_name, vcol.data_type, vcol.domain)
                            else: other_v = new_vertex_color(o, self.vcol_name)
                            set_obj_vertex_colors(o, other_v.name, (1.0, 1.0, 1.0, 1.0))
                            set_active_vertex_color(o, other_v)
                        except: pass

        # Add new mask
        mask = add_new_mask(layer, name, self.type, self.texcoord_type, self.uv_map, image, vcol, blend_type=self.blend_type)

        # Enable edit mask
        if self.type in {'IMAGE', 'VCOL'}:
            mask.active_edit = True

        rearrange_layer_nodes(layer)
        reconnect_layer_nodes(layer)

        rearrange_yp_nodes(layer.id_data)
        reconnect_yp_nodes(layer.id_data)

        # Make sure all layers which used the opened image is using correct linear color
        if self.type == 'IMAGE':
            check_yp_linear_nodes(yp)

        ypui.layer_ui.expand_masks = True
        ypui.need_update = True

        return {'FINISHED'}

class YMoveLayerMask(bpy.types.Operator):
    bl_idname = "node.y_move_layer_mask"
    bl_label = "Move Layer Mask"
    bl_description = "Move layer mask"
    bl_options = {'REGISTER', 'UNDO'}

    direction : EnumProperty(
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
        swap_mask_fcurves(layer, index, new_index)

        # Dealing with transition bump
        tree = get_tree(layer)
        check_mask_mix_nodes(layer, tree)
        check_mask_source_tree(layer) #, bump_ch)
        #check_mask_image_linear_node(mask)

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
        mat = obj.active_material
        yp = layer.id_data.yp

        mask_type = mask.type

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

        if mask_type == 'COLOR_ID':

            # Check if color id vcol need to be removed or not
            objs = get_all_objects_with_same_materials(mat)
            if not is_colorid_vcol_still_being_used(objs):
                for o in objs:
                    ovcols = get_vertex_colors(o)
                    vcol = ovcols.get(COLOR_ID_VCOL_NAME)
                    if vcol: ovcols.remove(vcol)

        # Refresh viewport and image editor
        for area in bpy.context.screen.areas:
            if area.type in ['VIEW_3D', 'IMAGE_EDITOR', 'NODE_EDITOR']:
                area.tag_redraw()

        return {'FINISHED'}

def update_mask_active_edit(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    if self.halt_update: return

    # Only image mask can be edited
    #if self.active_edit and self.type not in {'IMAGE', 'VCOL'}:
    #    self.halt_update = True
    #    self.active_edit = False
    #    self.halt_update = False
    #    return

    yp = self.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer_idx = int(match.group(1))
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))

    # Disable other active edits
    if self.active_edit: 
        yp.halt_update = True
        for c in layer.channels:
            c.active_edit = False
            c.active_edit_1 = False

        for m in layer.masks:
            if m == self: continue
            #m.halt_update = True
            m.active_edit = False
            #m.halt_update = False

        yp.halt_update = False

    # Refresh
    yp.active_layer_index = layer_idx

def update_mask_channel_intensity_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    tree = get_tree(layer)

    mute = not self.enable or not mask.enable or not layer.enable_masks

    mix = tree.nodes.get(self.mix)
    if mix: mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value
    #dirs = [d for d in neighbor_directions]
    #dirs.extend(['pure', 'remains', 'normal'])
    dirs = ['pure', 'remains', 'normal']

    for d in dirs:
        mix = tree.nodes.get(getattr(self, 'mix_' + d))
        if mix: mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value

def update_mask_blur_vector(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self
    tree = get_tree(layer)

    if mask.enable_blur_vector:
        blur_vector = new_node(tree, mask, 'blur_vector', 'ShaderNodeGroup', 'Mask Blur Vector')
        blur_vector.node_tree = get_node_tree_lib(lib.BLUR_VECTOR)
        blur_vector.inputs[0].default_value = mask.blur_vector_factor / 100.0
    else:
        remove_node(tree, mask, 'blur_vector')

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

def update_mask_blur_vector_factor(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = self
    tree = get_tree(layer)

    blur_vector = tree.nodes.get(mask.blur_vector)

    if blur_vector:
        blur_vector.inputs[0].default_value = mask.blur_vector_factor / 100.0

def update_mask_intensity_value(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    tree = get_tree(layer)

    mute = not mask.enable or not layer.enable_masks

    mix = tree.nodes.get(mask.mix)
    if mix: mix.inputs[0].default_value = 0.0 if mute else mask.intensity_value

    for c in mask.channels:
        update_mask_channel_intensity_value(c, context)

def update_layer_mask_channel_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask = layer.masks[int(match.group(2))]
    tree = get_tree(layer)

    check_mask_mix_nodes(layer, tree, mask, self)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    #mute = not self.enable or not mask.enable or not layer.enable_masks

    #mix = tree.nodes.get(self.mix)
    #if mix:
    #    #if yp.disable_quick_toggle:
    #    #    mix.mute = mute
    #    #else: mix.mute = False
    #    mix.mute = mute

    #dirs = [d for d in neighbor_directions]
    #dirs.extend(['pure', 'remains', 'normal'])

    #for d in dirs:
    #    mix = tree.nodes.get(getattr(self, 'mix_' + d))
    #    if mix: 
    #        #if yp.disable_quick_toggle:
    #        #    mix.mute = mute
    #        #else: mix.mute = False
    #        mix.mute = mute

    update_mask_channel_intensity_value(self, context)

def update_layer_mask_enable(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    check_mask_mix_nodes(layer, tree, self)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    #for ch in self.channels:
    #    update_layer_mask_channel_enable(ch, context)

    self.active_edit = self.enable and self.type in {'IMAGE', 'VCOL', 'COLOR_ID'}

def update_enable_layer_masks(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    #for mask in self.masks:
    #    update_layer_mask_enable(mask, context)
    check_mask_mix_nodes(self)

    rearrange_layer_nodes(self)
    reconnect_layer_nodes(self)

def update_mask_texcoord_type(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))
    tree = get_tree(layer)

    # Update global uv
    check_uv_nodes(yp)

    # Update layer tree inputs
    yp_dirty = True if check_layer_tree_ios(layer, tree) else False

    set_mask_uv_neighbor(tree, layer, self, mask_idx)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    if yp_dirty:
        rearrange_yp_nodes(self.id_data)
        reconnect_yp_nodes(self.id_data)

def update_mask_uv_name(self, context):
    obj = context.object
    yp = self.id_data.yp
    ypui = context.window_manager.ypui
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    mask_idx = int(match.group(2))
    active_layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)
    mask = self

    if mask.type in {'HEMI', 'OBJECT_INDEX', 'COLOR_ID'} or mask.texcoord_type != 'UV':
        return

    # Cannot use temp uv as standard uv
    if mask.uv_name in {TEMP_UV, ''}:
        if len(yp.uvs) > 0:
            for uv in yp.uvs:
                mask.uv_name = uv.name
                break
    
    # Update uv layer
    if mask.active_edit and obj.type == 'MESH' and layer == active_layer:

        if mask.segment_name != '':
            refresh_temp_uv(obj, mask)
        else:

            if hasattr(obj.data, 'uv_textures'):
                uv_layers = obj.data.uv_textures
            else: uv_layers = obj.data.uv_layers

            uv_layers.active = uv_layers.get(mask.uv_name)

    # Update global uv
    dirty = check_uv_nodes(yp)

    # Update layer tree inputs
    yp_dirty = True if check_layer_tree_ios(layer, tree) else False

    # Update neighbor uv if mask bump is active
    #if dirty or yp_dirty:
    #if set_mask_uv_neighbor(tree, layer, self, mask_idx) or dirty or yp_dirty:

    set_mask_uv_neighbor(tree, layer, self, mask_idx)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    if yp_dirty:
        rearrange_yp_nodes(self.id_data)
        reconnect_yp_nodes(self.id_data)

def update_mask_hemi_space(self, context):
    if self.type != 'HEMI': return

    source = get_mask_source(self)
    trans = source.node_tree.nodes.get('Vector Transform')
    if trans: trans.convert_from = self.hemi_space

def update_mask_hemi_use_prev_normal(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)

    check_layer_tree_ios(layer, tree)
    check_layer_bump_process(layer, tree)

    rearrange_layer_nodes(layer)
    reconnect_layer_nodes(layer)

    reconnect_yp_nodes(layer.id_data)

def update_mask_hemi_camera_ray_mask(self, context):
    yp = self.id_data.yp

    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]

    tree = get_mask_tree(self)
    source = get_mask_source(self)

    if source:

        # Check if source has the inputs, if not reload the node
        if 'Camera Ray Mask' not in source.inputs:
            source = replace_new_node(tree, self, 'source', 'ShaderNodeGroup', 'Mask Source', 
                    lib.HEMI, force_replace=True)
            duplicate_lib_node_tree(source)
            trans = source.node_tree.nodes.get('Vector Transform')
            if trans: trans.convert_from = self.hemi_space

            rearrange_layer_nodes(layer)
            reconnect_layer_nodes(layer)

        source.inputs['Camera Ray Mask'].default_value = 1.0 if self.hemi_camera_ray_mask else 0.0

def update_mask_name(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    src = get_mask_source(self)

    # Also update layer name if mask name is renamed in certain pattern
    m = re.match(r'^Mask\s.*\((.+)\)$', self.name)
    if m:
        old_layer_name = layer.name
        new_layer_name = m.group(1)

        yp.halt_update = True
        layer.name = new_layer_name

        # Also update other mask names
        for mask in layer.masks:
            if mask == self: continue
            mm = re.match(r'^Mask\s.*\((.+)\)$', mask.name)
            if mm:
                mask.name = mask.name.replace(mm.group(1), new_layer_name)

        yp.halt_update = False

    if self.type == 'IMAGE' and self.segment_name != '': return
    change_layer_name(yp, context.object, src, self, layer.masks)

def update_mask_blend_type(self, context):

    yp = self.id_data.yp
    if yp.halt_update: return
    match = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', self.path_from_id())
    layer = yp.layers[int(match.group(1))]
    tree = get_tree(layer)
    mask = self

    #dirs = [d for d in neighbor_directions]
    #dirs.extend(['pure', 'remains', 'normal'])

    #for c in mask.channels:
    #    mix = tree.nodes.get(c.mix)
    #    if mix: mix.blend_type = mask.blend_type
    #    for d in dirs:
    #        mix = tree.nodes.get(getattr(c, 'mix_' + d))
    #        if mix: mix.blend_type = mask.blend_type

    check_mask_mix_nodes(layer, tree, mask)

    # Rearrange nodes
    rearrange_layer_nodes(layer)

    # Reconnect nodes
    reconnect_layer_nodes(layer)

def update_mask_object_index(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return

    source = get_mask_source(self)
    source.inputs[0].default_value = self.object_index

def update_mask_transform(self, context):
    yp = self.id_data.yp
    if yp.halt_update: return
    update_mapping(self)

def update_mask_color_id(self, context):
    yp = self.id_data.yp
    mask = self

    if mask.type != 'COLOR_ID': return

    source = get_mask_source(mask)
    col = (mask.color_id[0], mask.color_id[1], mask.color_id[2], 1.0)
    if source: source.inputs[0].default_value = col

class YLayerMaskChannel(bpy.types.PropertyGroup):
    enable : BoolProperty(default=True, update=update_layer_mask_channel_enable)

    # Multiply between mask channels
    mix : StringProperty(default='')

    # Pure mask without any extra multiplier or uv shift, useful for height process
    mix_pure : StringProperty(default='')

    # Remaining masks after chain
    mix_remains : StringProperty(default='')

    # Normal and height has its own alpha if using group, this one is for normal
    mix_normal : StringProperty(default='')

    # To limit mix value to not go above original channel value, useful for group layer
    mix_limit : StringProperty(default='')
    mix_limit_normal : StringProperty(default='')

    # Bump related
    #mix_n : StringProperty(default='')
    #mix_s : StringProperty(default='')
    #mix_e : StringProperty(default='')
    #mix_w : StringProperty(default='')

    # UI related
    expand_content : BoolProperty(default=False)

class YLayerMask(bpy.types.PropertyGroup):

    name : StringProperty(default='', update=update_mask_name)

    halt_update : BoolProperty(default=False)
    
    group_node : StringProperty(default='')

    enable : BoolProperty(
            name='Enable Mask', 
            description = 'Enable mask',
            default=True, update=update_layer_mask_enable)

    active_edit : BoolProperty(
            name='Active mask for editing or preview', 
            description='Active mask for editing or preview', 
            default=False,
            update=update_mask_active_edit)

    #active_vcol_edit : BoolProperty(
    #        name='Active vertex color for editing', 
    #        description='Active vertex color for editing', 
    #        default=False,
    #        update=update_mask_active_vcol_edit)

    type : EnumProperty(
            name = 'Mask Type',
            items = mask_type_items,
            default = 'IMAGE')

    texcoord_type : EnumProperty(
        name = 'Texture Coordinate Type',
        items = texcoord_type_items,
        default = 'UV',
        update=update_mask_texcoord_type)

    hemi_space : EnumProperty(
            name = 'Fake Lighting Space',
            description = 'Fake lighting space',
            items = hemi_space_items,
            default = 'OBJECT',
            update=update_mask_hemi_space)

    hemi_camera_ray_mask : BoolProperty(
            name = 'Camera Ray Mask',
            description = "Use Camera Ray value so the back of the mesh won't be affected by fake lighting",
            default = False, update=update_mask_hemi_camera_ray_mask)

    hemi_use_prev_normal : BoolProperty(
            name = 'Use previous Normal',
            description = 'Take account previous Normal',
            default = False, update=update_mask_hemi_use_prev_normal)

    uv_name : StringProperty(default='', update=update_mask_uv_name)

    blend_type : EnumProperty(
        name = 'Blend',
        items = mask_blend_type_items,
        default = 'MULTIPLY',
        update = update_mask_blend_type)

    intensity_value : FloatProperty(
            name = 'Mask Intensity Factor', 
            description = 'Mask Intensity Factor',
            default=1.0, min=0.0, max=1.0, subtype='FACTOR',
            update = update_mask_intensity_value)

    # Transform
    translation : FloatVectorProperty(
            name='Translation', size=3, precision=3, 
            default=(0.0, 0.0, 0.0),
            update=update_mask_transform
            ) #, step=1)

    rotation : FloatVectorProperty(
            name='Rotation', subtype='AXISANGLE', size=3, precision=3, unit='ROTATION', 
            default=(0.0, 0.0, 0.0),
            update=update_mask_transform
            ) #, step=3)

    scale : FloatVectorProperty(
            name='Scale', size=3, precision=3, 
            default=(1.0, 1.0, 1.0),
            update=update_mask_transform,
            ) #, step=3)

    enable_blur_vector : BoolProperty(
            name = 'Enable Blur Vector',
            description = "Enable blur vector",
            default = False, update=update_mask_blur_vector)

    blur_vector_factor : FloatProperty(
            name = 'Blur Vector Factor', 
            description = 'Mask Intensity Factor',
            default=1.0, min=0.0, max=100.0,
            update=update_mask_blur_vector_factor)

    color_id : FloatVectorProperty(
            name='Color ID', size=3,
            subtype='COLOR',
            default=(1.0, 0.0, 1.0),
            min=0.0, max=1.0,
            update=update_mask_color_id,
            )

    segment_name : StringProperty(default='')

    channels : CollectionProperty(type=YLayerMaskChannel)

    modifiers : CollectionProperty(type=MaskModifier.YMaskModifier)

    # For object index
    object_index : IntProperty(
            name = 'Object Index',
            description = 'Object Pass Index',
            default = 0,
            min=0,
            update=update_mask_object_index)

    # For temporary bake
    use_temp_bake : BoolProperty(
            name = 'Use Temporary Bake',
            description = 'Use temporary bake, it can be useful for prevent glitch on cycles',
            default = False,
            )

    original_type : EnumProperty(
            name = 'Original Mask Type',
            items = mask_type_items,
            default = 'IMAGE')

    # For fake lighting

    hemi_vector : FloatVectorProperty(
            name='Cache Hemi vector', size=3, precision=3,
            default=(0.0, 0.0, 1.0))

    # Nodes
    source : StringProperty(default='')
    source_n : StringProperty(default='')
    source_s : StringProperty(default='')
    source_e : StringProperty(default='')
    source_w : StringProperty(default='')

    uv_map : StringProperty(default='')
    uv_neighbor : StringProperty(default='')
    mapping : StringProperty(default='')
    blur_vector : StringProperty(default='')

    linear : StringProperty(default='')

    # Only useful for merging mask for now
    mix : StringProperty(default='')

    need_temp_uv_refresh : BoolProperty(default=False)

    tangent : StringProperty(default='')
    bitangent : StringProperty(default='')
    tangent_flip : StringProperty(default='')
    bitangent_flip : StringProperty(default='')

    # UI related
    expand_content : BoolProperty(default=False)
    expand_channels : BoolProperty(default=False)
    expand_source : BoolProperty(default=False)
    expand_vector : BoolProperty(default=False)

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
