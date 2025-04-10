import bpy, time, random, re
from bpy.props import *
from .common import *
from .subtree import *
from . import BakeInfo, UDIM

def is_tile_available(x, y, width, height, atlas):

    start_x = width * x
    end_x = start_x + width - 1

    start_y = height * y
    end_y = start_y + height - 1

    for segment in atlas.segments:

        segment_start_x = segment.width * segment.tile_x
        segment_end_x = segment_start_x + segment.width - 1

        segment_start_y = segment.height * segment.tile_y
        segment_end_y = segment_start_y + segment.height - 1

        if (
            ((start_x >= segment_start_x and start_x <= segment_end_x) or 
            (end_x <= segment_end_x and end_x >= segment_start_x)) 
            and
            ((start_y >= segment_start_y and start_y <= segment_end_y) or 
            (end_y <= segment_end_y and end_y >= segment_start_y)) 
            ):
            return False

    return True

def get_available_tile(width, height, atlas):
    atlas_img = atlas.id_data

    num_x = int(atlas_img.size[0] / width)
    num_y = int(atlas_img.size[1] / height)

    for y in range(num_y):
        for x in range(num_x):
            if is_tile_available(x, y, width, height, atlas):
                return [x, y]

    return []

def create_image_atlas(color='BLACK', size=8192, hdr=False, name=''):

    if name != '':
        name = '~' + name + ' Image Atlas'
    else: name = '~Image Atlas'

    if hdr:
        name += ' HDR'

    name = get_unique_name(name, bpy.data.images)

    img = bpy.data.images.new(
        name=name, width=size, height=size,
        alpha=True, float_buffer=hdr
    )

    if color == 'BLACK':
        img.generated_color = (0, 0, 0, 1)
        img.colorspace_settings.name = get_noncolor_name()
    elif color == 'WHITE':
        img.generated_color = (1, 1, 1, 1)
        img.colorspace_settings.name = get_noncolor_name()
    else: img.generated_color = (0, 0, 0, 0)

    img.yia.is_image_atlas = True
    img.yia.color = color
    #img.yia.float_buffer = hdr
    #if hdr:
    #img.colorspace_settings.name = get_noncolor_name()

    return img

def create_image_atlas_segment(atlas, width, height):

    name = get_unique_name('Segment', atlas.segments)

    segment = None

    tile = get_available_tile(width, height, atlas)
    if tile:
        segment = atlas.segments.add()
        segment.name = name
        segment.width = width
        segment.height = height
        segment.tile_x = tile[0]
        segment.tile_y = tile[1]

    return segment

def clear_segment(segment):
    img = segment.id_data
    atlas = img.yia

    if atlas.color == 'BLACK':
        col = (0.0, 0.0, 0.0, 1.0)
    elif atlas.color == 'WHITE':
        col = (1.0, 1.0, 1.0, 1.0)
    else:
        col = (0.0, 0.0, 0.0, 0.0)

    set_image_pixels(img, col, segment)

def clear_unused_segments(atlas):

    # Recolor unused segments
    for segment in atlas.segments:
        if segment.unused:
            clear_segment(segment)

    # Remove unused segments
    for i, segment in reversed(list(enumerate(atlas.segments))):
        if segment.unused:
            atlas.segments.remove(i)

def is_there_any_unused_segments(atlas, width, height):
    for segment in atlas.segments:
        if segment.unused and segment.width >= width and segment.height >= height:
            return True
    return False

def check_need_of_erasing_segments(yp, color='BLACK', width=1024, height=1024, hdr=False):

    ypup = get_user_preferences()
    images = get_yp_images(yp) if ypup.unique_image_atlas_per_yp else bpy.data.images

    for img in images:
        #if img.yia.is_image_atlas and img.yia.color == color and img.yia.float_buffer == hdr:
        if img.yia.is_image_atlas and img.yia.color == color and img.is_float == hdr:
            if not get_available_tile(width, height, img.yia) and is_there_any_unused_segments(img.yia, width, height):
                return img

    return None

def get_set_image_atlas_segment(width, height, color='BLACK', hdr=False, img_from=None, segment_from=None, yp=None):

    ypup = get_user_preferences()
    segment = None

    # Get bunch of images
    if yp and ypup.unique_image_atlas_per_yp:
        images = get_yp_images(yp)
        name = yp.id_data.name
    else:
        images = bpy.data.images
        name = ''

    # Search for available image atlas
    for img in images:
        #if img.yia.is_image_atlas and img.yia.color == color and img.yia.float_buffer == hdr:
        if img.yia.is_image_atlas and img.yia.color == color and img.is_float == hdr:
            segment = create_image_atlas_segment(img.yia, width, height)
            if segment: 
                #return segment
                break
            else:
                # This is where unused segments should be erased 
                pass

    if not segment:
        if hdr: new_atlas_size = ypup.hdr_image_atlas_size
        else: new_atlas_size = ypup.image_atlas_size

        # If proper image atlas can't be found, create new one
        img = create_image_atlas(color, new_atlas_size, hdr, name)
        segment = create_image_atlas_segment(img.yia, width, height)
        #if segment: return segment

    if img_from and segment_from:
        copy_image_pixels(img_from, img, segment, segment_from)

    return segment

def get_entities_with_specific_segment(yp, segment):

    entities = []

    layer_ids = get_layer_ids_with_specific_segment(yp, segment)
    for li in layer_ids:
        layer = yp.layers[li]
        entities.append(layer)

    for layer in yp.layers:
        masks = get_masks_with_specific_segment(layer, segment)
        entities.extend(masks)

    return entities

def replace_segment_with_image(yp, segment, image, uv_name=''):

    entities = get_entities_with_specific_segment(yp, segment)

    for entity in entities:
        # Replace image
        source = get_entity_source(entity)
        source.image = image
        entity.segment_name = ''

        # Clear mapping and set new uv map
        clear_mapping(entity)
        if uv_name != '' and entity.uv_name != uv_name:
            entity.uv_name = uv_name

    # Remove segment
    if segment.id_data.source == 'TILED':
        UDIM.remove_udim_atlas_segment_by_name(segment.id_data, segment.name, yp)
    else:
        # Make segment unused
        segment.unused = True

    return entities

#class YUVTransformTest(bpy.types.Operator):
#    bl_idname = "wm.y_uv_transform_test"
#    bl_label = "UV Transform Test"
#    bl_description = "UV Transform Test"
#    bl_options = {'REGISTER', 'UNDO'}
#
#    @classmethod
#    def poll(cls, context):
#        return True
#
#    def execute(self, context):
#        T = time.time()
#
#        ob = context.object
#
#        #for face in ob.data.polygons:
#        #    for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
#        #        uv_coords = ob.data.uv_layers.active.data[loop_idx].uv
#        #        #print("face idx: %i, vert idx: %i, uvs: %f, %f" % (face.index, vert_idx, uv_coords.x, uv_coords.y))
#        #        pass
#        
#        # Or just cycle all loops
#        for loop in ob.data.loops :
#            uv_coords = ob.data.uv_layers.active.data[loop.index].uv
#            uv_coords.x += 0.1
#            #print(uv_coords)
#
#        print('INFO: UV Map of', ob.name, 'is updated in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
#
#        return {'FINISHED'}

def get_segment_mapping(segment, image):

    scale_x = segment.width / image.size[0]
    scale_y = segment.height / image.size[1]

    offset_x = scale_x * segment.tile_x
    offset_y = scale_y * segment.tile_y

    return scale_x, scale_y, offset_x, offset_y

def set_segment_mapping(entity, segment, image, use_baked=False):

    if image.source == 'TILED':
        UDIM.set_udim_segment_mapping(entity, segment, image, use_baked)
        return
    
    scale_x, scale_y, offset_x, offset_y = get_segment_mapping(segment, image)

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: mapping = get_layer_mapping(entity, get_baked=use_baked)
    else: mapping = get_mask_mapping(entity, get_baked=use_baked)

    if mapping:
        if is_bl_newer_than(2, 81):
            mapping.inputs[3].default_value[0] = scale_x
            mapping.inputs[3].default_value[1] = scale_y

            mapping.inputs[1].default_value[0] = offset_x
            mapping.inputs[1].default_value[1] = offset_y
        else:
            mapping.scale[0] = scale_x
            mapping.scale[1] = scale_y

            mapping.translation[0] = offset_x
            mapping.translation[1] = offset_y

class YNewImageAtlasSegmentTest(bpy.types.Operator):
    bl_idname = "wm.y_new_image_atlas_segment_test"
    bl_label = "New Image Atlas Segment Test"
    bl_description = "New Image Atlas segment test"
    bl_options = {'REGISTER', 'UNDO'}

    #image_atlas_name = StringProperty(
    #        name = 'Image Atlas',
    #        description = 'Image atlas name',
    #        default='')

    #image_atlas_coll = CollectionProperty(type=bpy.types.PropertyGroup)
    color = EnumProperty(
        name = 'Altas Base Color',
        items = (
            ('WHITE', 'White', ''),
            ('BLACK', 'Black', ''),
            ('TRANSPARENT', 'Transparent', '')
        ),
        default = 'BLACK'
    )

    width = IntProperty(name='Width', default=128, min=1, max=4096)
    height = IntProperty(name='Height', default=128, min=1, max=4096)

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):

        # Update image atlas collections
        #self.image_atlas_coll.clear()
        #imgs = bpy.data.images
        #for img in imgs:
        #    if img.yia.is_image_atlas:
        #        self.image_atlas_coll.add().name = img.name

        return context.window_manager.invoke_props_dialog(self, width=320)

    def check(self, context):
        return True

    def draw(self, context):
        col = self.layout.column()
        #col.label('Noiss')
        #col.prop_search(self, "image_atlas_name", self, "image_atlas_coll", icon='IMAGE_DATA')
        col.prop(self, "color")
        col.prop(self, "width")
        col.prop(self, "height")

    def execute(self, context):

        T = time.time()

        #if self.image_atlas_name == '':
        #    #atlas_img = create_image_atlas(color='BLACK', size=16384)
        #    atlas_img = create_image_atlas(color='BLACK', size=1024)
        #else: atlas_img = bpy.data.images.get(self.image_atlas_name)
        segment = get_set_image_atlas_segment(
            self.width, self.height, self.color, hdr=False
        )

        atlas_img = segment.id_data
        atlas = atlas_img.yia

        #width = 128
        #height = 128

        #segment = create_image_atlas_segment(atlas, self.width, self.height)

        #print(segment)

        if segment and True:
            col = [random.random(), random.random(), random.random(), 1.0]

            start_x = self.width * segment.tile_x
            end_x = start_x + self.width

            start_y = self.height * segment.tile_y
            end_y = start_y + self.height

            pxs = list(atlas_img.pixels)
            #pxs = numpy.array(atlas_img.pixels) #, dtype='float16')

            for y in range(start_y, end_y):

                offset_y = atlas_img.size[0] * 4 * y
                #atlas_img.pixels[offset_y + start_x * 4 : offset_y + end_x * 4] = col * self.width

                for x in range(start_x, end_x):
                    for i in range(3):
                        pxs[offset_y + (x * 4) + i] = col[i]
                        pxs[offset_y + (x * 4) + 3] = 1.0

            atlas_img.pixels = pxs

        # Update image editor
        update_image_editor_image(context, atlas_img)

        print('INFO: Segment is created in', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YRefreshTransformedLayerUV(bpy.types.Operator):
    bl_idname = "wm.y_refresh_transformed_uv"
    bl_label = "Refresh Layer UV with Custom Transformation"
    bl_description = "Refresh layer UV with custom transformation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')

    def execute(self, context):

        obj = context.object
        layer = context.layer
        yp = layer.id_data.yp
        ypui = context.window_manager.ypui

        uv_layers = get_uv_layers(obj)

        image, uv_name, src_of_img, entity, mapping, vcol = get_active_image_and_stuffs(obj, yp)
        if image:
            refresh_temp_uv(obj, src_of_img)
            update_image_editor_image(context, image)
            context.scene.tool_settings.image_paint.canvas = image
        else:
            uv_name = get_relevant_uv(obj, yp)
            if uv_name != '':
                uv = uv_layers.get(uv_name)
                if uv: uv_layers.active = uv

        # Update tangent sign if height channel and tangent sign hack is enabled
        height_ch = get_root_height_channel(yp)
        if height_ch and is_tangent_sign_hacks_needed(yp):
            for uv in yp.uvs:
                refresh_tangent_sign_vcol(obj, uv.name)

        yp.need_temp_uv_refresh = False

        return {'FINISHED'}

class YBackToOriginalUV(bpy.types.Operator):
    bl_idname = "wm.y_back_to_original_uv"
    bl_label = "Back to Original UV"
    bl_description = "Transformed UV detected, your changes will be lost if you edit on this UV.\nClick this button to go back to original UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')

    def execute(self, context):

        obj = context.object
        mat = get_active_material()
        objs = get_all_objects_with_same_materials(mat, selected_only=True)
        layer = context.layer
        yp = layer.id_data.yp
        ypui = context.window_manager.ypui

        # Get active image
        image, uv_name, src_of_img, entity, mapping, vcol = get_active_image_and_stuffs(obj, yp)

        if not src_of_img: 
            try:
                src_of_img = yp.layers[yp.active_layer_index]
            except Exception as e:
                print(e)
                return {'CANCELLED'}

        for ob in objs:
            uv_layers = get_uv_layers(ob)

            for uv in uv_layers:
                if uv.name == src_of_img.uv_name:

                    if uv_layers.active != uv_layers.get(src_of_img.uv_name):
                        uv_layers.active = uv_layers.get(src_of_img.uv_name)

                if uv.name == TEMP_UV:
                    uv_layers.remove(uv)

            # Update tangent sign if height channel and tangent sign hack is enabled
            height_ch = get_root_height_channel(yp)
            if height_ch and is_tangent_sign_hacks_needed(yp):
                for uv in yp.uvs:
                    refresh_tangent_sign_vcol(ob, uv.name)

        # Hide active image
        if image:
            update_image_editor_image(context, None)
            context.scene.tool_settings.image_paint.canvas = None

        #yp.need_temp_uv_refresh = True

        return {'FINISHED'}

class YConvertToImageAtlas(bpy.types.Operator):
    bl_idname = "wm.y_convert_to_image_atlas"
    bl_label = "Convert Image to Image Atlas"
    bl_description = "Convert image to image atlas (useful to avoid material texture limit)"
    bl_options = {'REGISTER', 'UNDO'}

    all_images = BoolProperty(
        name = 'All Images',
        description = 'Convert all images instead of only the active one',
        default = False
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and hasattr(context, 'entity')

    def execute(self, context):
        mat = get_active_material()
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if self.all_images:
            entities, images, segment_names, segment_name_props = get_yp_entities_images_and_segments(yp)
        else:
            mapping = get_entity_mapping(context.entity)
            if is_transformed(mapping, context.entity) and not context.entity.use_baked:
                self.report({'ERROR'}, "Cannot convert transformed image!")
                return {'CANCELLED'}

            images = [context.image]
            entities = [[context.entity]]
            segment_name_prop = 'segment_name' if not context.entity.use_baked else 'baked_segment_name'
            segment_name_props = [[segment_name_prop]]
            segment_name = getattr(context.entity, segment_name_prop)
            segment_names = [segment_name]

        for i, image in enumerate(images):
            if image.yia.is_image_atlas or image.yua.is_udim_atlas: continue

            used_by_masks = False
            valid_entities = []
            for j, entity in enumerate(entities[i]):

                # Check if entity is baked to image atlas
                use_baked = segment_name_props[i][j] == 'baked_segment_name'

                # Mask will use different type of image atlas
                m = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
                if m: used_by_masks = True

                # Transformed mapping on entity is not valid for conversion
                mapping = get_entity_mapping(entity)
                if use_baked or not is_transformed(mapping, entity):
                    valid_entities.append(entity)

            if not any(valid_entities):
                continue

            # Image used by masks will use black image atlas instead of transparent so it will use linear color by default
            color = 'BLACK' if used_by_masks else 'TRANSPARENT'
            colorspace = get_noncolor_name() if used_by_masks else get_srgb_name()

            # Get segment
            if image.source == 'TILED':

                # Make sure image has filepath
                if image.filepath == '': UDIM.initial_pack_udim(image)

                objs = get_all_objects_with_same_materials(mat, True, valid_entities[0].uv_name)
                tilenums = UDIM.get_tile_numbers(objs, valid_entities[0].uv_name)
                new_segment = UDIM.get_set_udim_atlas_segment(tilenums, color=image.yui.base_color, colorspace=colorspace, hdr=image.is_float, yp=yp, source_image=image)
                ia_image = new_segment.id_data
            else:
                new_segment = get_set_image_atlas_segment(image.size[0], image.size[1], color, hdr=image.is_float)

                # Copy image to segment
                ia_image = new_segment.id_data
                copy_image_pixels(image, ia_image, new_segment)

            # Copy bake info
            if image.y_bake_info.is_baked:
                copy_id_props(image.y_bake_info, new_segment.bake_info)
                new_segment.bake_info.use_image_atlas = True

            for j, entity in enumerate(valid_entities):
                # Set image atlas to entity
                use_baked = segment_name_props[i][j] == 'baked_segment_name'
                source = get_entity_source(entity, get_baked=use_baked)
                source.image = ia_image

                # Set segment name
                #entity.segment_name = new_segment.name
                setattr(entity, segment_name_props[i][j], new_segment.name)

                # Make sure uniform scaling is not used
                if entity.enable_uniform_scale:
                    entity.enable_uniform_scale = False

                # Set image to editor
                if entity == context.entity:
                    update_image_editor_image(bpy.context, ia_image)
                    context.scene.tool_settings.image_paint.canvas = ia_image

                # Update mapping
                update_mapping(entity, use_baked=use_baked)
                set_uv_neighbor_resolution(entity, use_baked=use_baked)

            # Remove image if no one using it
            if image.users == 0:
                remove_datablock(bpy.data.images, image)

        # Refresh linear nodes
        check_yp_linear_nodes(yp)

        return {'FINISHED'}

class YConvertToStandardImage(bpy.types.Operator):
    bl_idname = "wm.y_convert_to_standard_image"
    bl_label = "Convert Image Atlas to standard image"
    bl_description = "Convert image atlas to standard image"
    bl_options = {'REGISTER', 'UNDO'}

    all_images = BoolProperty(
        name = 'All Images',
        description = 'Convert all images instead of only the active one',
        default = False
    )

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'image') and context.image and hasattr(context, 'entity')

    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        if self.all_images:
            entities, images, segment_names, segment_name_props = get_yp_entities_images_and_segments(yp)
        else:
            images = [context.image]

            segment_name_prop = 'segment_name' if not context.entity.use_baked else 'baked_segment_name'
            segment_name_props = [[segment_name_prop]]
            segment_name = getattr(context.entity, segment_name_prop)

            if context.image.yia.is_image_atlas:
                segment = context.image.yia.segments.get(segment_name)
            else: segment = context.image.yua.segments.get(segment_name)

            entities = [get_entities_with_specific_segment(yp, segment)]
            segment_names = [segment_name]

        image_atlases = []

        for i, image in enumerate(images):
            if not image.yia.is_image_atlas and not image.yua.is_udim_atlas: continue

            if image.yia.is_image_atlas:
                segment = image.yia.segments.get(segment_names[i])
            else: segment = image.yua.segments.get(segment_names[i])

            if not segment: continue

            # Create new image based on image atlas
            if image.yia.is_image_atlas:
                new_image = bpy.data.images.new(
                    name=entities[i][0].name, width=segment.width, height=segment.height,
                    alpha=True, float_buffer=image.is_float
                )
            else:
                new_image = bpy.data.images.new(
                    name=entities[i][0].name, width=image.size[0], height=image.size[1],
                    alpha=True, float_buffer=image.is_float, tiled=True
                )

                atlas_tilenums = UDIM.get_udim_segment_tilenums(segment)
                index = UDIM.get_udim_segment_index(image, segment)
                offset = get_udim_segment_mapping_offset(segment) * 10
                copy_dict = {}
                tilenums = []
                for atilenum in atlas_tilenums:
                    atile = image.tiles.get(atilenum)
                    tilenum = atilenum - offset
                    tilenums.append(tilenum)
                    copy_dict[atilenum] = tilenum
                    UDIM.fill_tile(new_image, tilenum, image.yui.base_color, atile.size[0], atile.size[1])

                UDIM.initial_pack_udim(new_image)

            new_image.colorspace_settings.name = image.colorspace_settings.name

            # Copy the pixels
            if image.yia.is_image_atlas:
                copy_image_pixels(image, new_image, None, segment)
            else:
                UDIM.copy_tiles(image, new_image, copy_dict)

                # Pack image
                UDIM.initial_pack_udim(new_image)

            # Copy bake info
            if segment.bake_info.is_baked:
                copy_id_props(segment.bake_info, new_image.y_bake_info)
                new_image.y_bake_info.use_image_atlas = False

            if image.yia.is_image_atlas:
                # Mark unused to the segment
                segment.unused = True
            else:
                UDIM.remove_udim_atlas_segment_by_name(image, segment.name, yp)

            for j, entity in enumerate(entities[i]):

                # Set new image to entity
                use_baked = segment_name_props[i][j] == 'baked_segment_name'
                source = get_entity_source(entity, get_baked=use_baked)
                source.image = new_image
                clear_mapping(entity, use_baked=use_baked)
                entity.segment_name = ''
                setattr(entity, segment_name_props[i][j], '')

                # Set image to editor
                if entity == context.entity:
                    update_image_editor_image(context, new_image)
                    context.scene.tool_settings.image_paint.canvas = new_image

                # Set UV Neighbor resolution
                set_uv_neighbor_resolution(entity)

            if image not in image_atlases:
                image_atlases.append(image)

        # Remove unused image atlas
        for ia_image in image_atlases:
            still_used = False

            if ia_image.yia.is_image_atlas:
                for segment in ia_image.yia.segments:
                    if not segment.unused:
                        still_used = True
                        break
            else:
                if len(ia_image.yua.segments) > 0:
                    still_used = True

            if not still_used:
                remove_datablock(bpy.data.images, ia_image)

        # Refresh linear nodes
        #check_yp_linear_nodes(yp)

        return {'FINISHED'}

class YImageAtlasSegment(bpy.types.PropertyGroup):

    name = StringProperty(
        name = 'Name',
        description = 'Name of Image Atlas Segments',
        default = ''
    )

    tile_x = IntProperty(default=0)
    tile_y = IntProperty(default=0)

    width = IntProperty(default=1024)
    height = IntProperty(default=1024)

    unused = BoolProperty(default=False)

    bake_info = PointerProperty(type=BakeInfo.YBakeInfoProps)

class YImageAtlas(bpy.types.PropertyGroup):
    name = StringProperty(
        name = 'Name',
        description = 'Name of Image Atlas',
        default = ''
    )

    is_image_atlas = BoolProperty(default=False)

    color = EnumProperty(
        name = 'Atlas Base Color',
        items = (
            ('WHITE', 'White', ''),
            ('BLACK', 'Black', ''),
            ('TRANSPARENT', 'Transparent', '')
        ),
        default = 'BLACK'
    )

    #float_buffer = BoolProperty(default=False)

    segments = CollectionProperty(type=YImageAtlasSegment)

def register():
    #bpy.utils.register_class(YUVTransformTest)
    bpy.utils.register_class(YNewImageAtlasSegmentTest)
    bpy.utils.register_class(YRefreshTransformedLayerUV)
    bpy.utils.register_class(YBackToOriginalUV)
    bpy.utils.register_class(YConvertToImageAtlas)
    bpy.utils.register_class(YConvertToStandardImage)
    #bpy.utils.register_class(YImageSegmentOtherObject)
    #bpy.utils.register_class(YImageSegmentBakeInfoProps)
    bpy.utils.register_class(YImageAtlasSegment)
    bpy.utils.register_class(YImageAtlas)

    bpy.types.Image.yia = PointerProperty(type=YImageAtlas)

def unregister():
    #bpy.utils.unregister_class(YUVTransformTest)
    bpy.utils.unregister_class(YNewImageAtlasSegmentTest)
    bpy.utils.unregister_class(YRefreshTransformedLayerUV)
    bpy.utils.unregister_class(YBackToOriginalUV)
    bpy.utils.unregister_class(YConvertToImageAtlas)
    bpy.utils.unregister_class(YConvertToStandardImage)
    #bpy.utils.unregister_class(YImageSegmentOtherObject)
    #bpy.utils.unregister_class(YImageSegmentBakeInfoProps)
    bpy.utils.unregister_class(YImageAtlasSegment)
    bpy.utils.unregister_class(YImageAtlas)
