import bpy, time, random, numpy
from bpy.props import *
from .common import *
from .subtree import *

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

def create_image_atlas(color='BLACK', size=8192, hdr=False):

    if hdr:
        name = get_unique_name('~Image Atlas HDR', bpy.data.images)
    else: name = get_unique_name('~Image Atlas', bpy.data.images)

    img = bpy.data.images.new(name=name, 
            width=size, height=size, alpha=True, float_buffer=hdr)

    if color == 'BLACK':
        img.generated_color = (0,0,0,1)
    elif color == 'WHITE':
        img.generated_color = (1,1,1,1)
    else: img.generated_color = (0,0,0,0)

    img.yia.is_image_atlas = True
    img.yia.color = color
    #img.yia.float_buffer = hdr

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

def clear_unused_segments(atlas):
    img = atlas.id_data

    pxs = list(img.pixels)

    if atlas.color == 'BLACK':
        col = (0.0, 0.0, 0.0, 1.0)
    elif atlas.color == 'WHITE':
        col = (1.0, 1.0, 1.0, 1.0)
    else:
        col = (0.0, 0.0, 0.0, 0.0)

    # Recolor unused segments
    for segment in atlas.segments:
        if segment.unused:

            start_x = segment.width * segment.tile_x
            end_x = start_x + segment.width

            start_y = segment.height * segment.tile_y
            end_y = start_y + segment.height

            for y in range(start_y, end_y):
                offset_y = img.size[0] * 4 * y
                for x in range(start_x, end_x):
                    for i in range(4):
                        pxs[offset_y + (x*4) + i] = col[i]

    img.pixels = pxs

    # Remove unused segments
    for i, segment in reversed(list(enumerate(atlas.segments))):
        if segment.unused:
            atlas.segments.remove(i)

def is_there_any_unused_segments(atlas, width, height):
    for segment in atlas.segments:
        if segment.unused and segment.width >= width and segment.height >= height:
            return True
    return False

def check_need_of_erasing_segments(color='BLACK', width=1024, height=1024, hdr=False):

    for img in bpy.data.images:
        #if img.yia.is_image_atlas and img.yia.color == color and img.yia.float_buffer == hdr:
        if img.yia.is_image_atlas and img.yia.color == color and img.is_float == hdr:
            if not get_available_tile(width, height, img.yia) and is_there_any_unused_segments(img.yia, width, height):
                return img

    return None

def copy_segment_pixels(img_from, segment_from, img_to, segment_to):

    if segment_from.width != segment_to.width or segment_from.height != segment_to.height:
        return

    from_pxs = list(img_from.pixels)
    if img_from == img_to:
        to_pxs = from_pxs
    else: to_pxs = list(img_to.pixels)

    width = segment_from.width
    height = segment_from.height

    from_start_x = width * segment_from.tile_x
    from_start_y = height * segment_from.tile_y

    to_start_x = width * segment_to.tile_x
    to_start_y = height * segment_to.tile_y

    for y in range(height):
        from_offset_y = img_from.size[0] * 4 * (y + from_start_y)
        to_offset_y = img_to.size[0] * 4 * (y + to_start_y)
        for x in range(width):
            from_offset_x = 4 * (x + from_start_x)
            to_offset_x = 4 * (x + to_start_x)
            for i in range(4):
                to_pxs[to_offset_y + to_offset_x + i] = from_pxs[from_offset_y + from_offset_x + i]

    img_to.pixels = to_pxs

def get_set_image_atlas_segment(width, height, color='BLACK', hdr=False, img_from=None, segment_from=None):

    if bpy.app.version_string.startswith('2.8'):
        ypup = bpy.context.preferences.addons[__package__].preferences
    else: ypup = bpy.context.user_preferences.addons[__package__].preferences

    segment = None

    # Serach for available image atlas
    for img in bpy.data.images:
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
        img = create_image_atlas(color, new_atlas_size, hdr)
        segment = create_image_atlas_segment(img.yia, width, height)
        #if segment: return segment

    if img_from and segment_from:
        copy_segment_pixels(img_from, segment_from, img, segment)

    return segment

#class YUVTransformTest(bpy.types.Operator):
#    bl_idname = "node.y_uv_transform_test"
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
#        print('INFO: UV Map of', ob.name, 'is updated at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
#
#        return {'FINISHED'}

class YNewImageAtlasSegmentTest(bpy.types.Operator):
    bl_idname = "node.y_new_image_atlas_segment_test"
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
            items = (('WHITE', 'White', ''),
                     ('BLACK', 'Black', ''),
                     ('TRANSPARENT', 'Transparent', '')),
            default = 'BLACK')

    width = IntProperty(name='Width', default = 128, min=1, max=4096)
    height = IntProperty(name='Height', default = 128, min=1, max=4096)

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
                self.width, self.height, self.color, 
                hdr=False)

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
                        pxs[offset_y + (x*4) + i] = col[i]
                        pxs[offset_y + (x*4) + 3] = 1.0

            atlas_img.pixels = pxs

        # Update image editor
        update_image_editor_image(context, atlas_img)

        print('INFO: Segment is created at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YRefreshTransformedLayerUV(bpy.types.Operator):
    bl_idname = "node.y_refresh_transformed_uv"
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

        image = None

        for mask in layer.masks:
            if mask.type == 'IMAGE' and mask.active_edit:
                refresh_temp_uv(obj, mask)
                source = get_mask_source(mask)
                image = source.image
                #return {'FINISHED'}
        
        if not image and layer.type == 'IMAGE':
            refresh_temp_uv(obj, layer)
            source = get_layer_source(layer)
            image = source.image

        if image:
            update_image_editor_image(context, image)
            context.scene.tool_settings.image_paint.canvas = image

        # Update tangent sign if height channel and tangent sign hack is enabled
        height_ch = get_root_height_channel(yp)
        if height_ch and yp.enable_tangent_sign_hacks:
            for uv in yp.uvs:
                refresh_tangent_sign_vcol(obj, uv.name)

        yp.need_temp_uv_refresh = False

        return {'FINISHED'}

class YBackToOriginalUV(bpy.types.Operator):
    bl_idname = "node.y_back_to_original_uv"
    bl_label = "Back to Original UV"
    bl_description = "Transformed UV detected, your changes will lost if you edit on this UV.\nClick this button to go back to original UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context, 'layer')

    def execute(self, context):

        obj = context.object
        layer = context.layer
        yp = layer.id_data.yp
        ypui = context.window_manager.ypui

        active = None
        image = None

        for mask in layer.masks:
            if mask.type == 'IMAGE' and mask.active_edit:
                source = get_mask_source(mask)
                image = source.image
                active = mask
                #return {'FINISHED'}
        
        if not active and layer.type == 'IMAGE':
            source = get_layer_source(layer)
            image = source.image
            active = layer

        if not active: return {'CANCELLED'}

        if hasattr(obj.data, 'uv_textures'): # Blender 2.7 only
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        #for i, uv in enumerate(uv_layers):
        for uv in uv_layers:
            if uv.name == active.uv_name:

                #if uv_layers.active_index != i:
                #    uv_layers.active_index = i
                if uv_layers.active != active:
                    uv_layers.active = uv_layers.get(active.uv_name)

            if uv.name == TEMP_UV:
                uv_layers.remove(uv)

        # Hide active image
        if image:
            update_image_editor_image(context, None)
            context.scene.tool_settings.image_paint.canvas = None

        # Update tangent sign if height channel and tangent sign hack is enabled
        height_ch = get_root_height_channel(yp)
        if height_ch and yp.enable_tangent_sign_hacks:
            for uv in yp.uvs:
                refresh_tangent_sign_vcol(obj, uv.name)

        yp.need_temp_uv_refresh = True

        return {'FINISHED'}

class YImageAtlasSegments(bpy.types.PropertyGroup):

    name = StringProperty(
            name='Name',
            description='Name of Image Atlas Segments',
            default='')

    tile_x = IntProperty(default=0)
    tile_y = IntProperty(default=0)

    width = IntProperty(default=1024)
    height = IntProperty(default=1024)

    unused = BoolProperty(default=False)

class YImageAtlas(bpy.types.PropertyGroup):
    name = StringProperty(
            name='Name',
            description='Name of Image Atlas',
            default='')

    is_image_atlas = BoolProperty(default=False)

    color = EnumProperty(
            name = 'Atlas Base Color',
            items = (('WHITE', 'White', ''),
                     ('BLACK', 'Black', ''),
                     ('TRANSPARENT', 'Transparent', '')),
            default = 'BLACK')

    #float_buffer = BoolProperty(default=False)

    segments = CollectionProperty(type=YImageAtlasSegments)

def register():
    #bpy.utils.register_class(YUVTransformTest)
    bpy.utils.register_class(YNewImageAtlasSegmentTest)
    bpy.utils.register_class(YRefreshTransformedLayerUV)
    bpy.utils.register_class(YBackToOriginalUV)
    bpy.utils.register_class(YImageAtlasSegments)
    bpy.utils.register_class(YImageAtlas)

    bpy.types.Image.yia = PointerProperty(type=YImageAtlas)

def unregister():
    #bpy.utils.unregister_class(YUVTransformTest)
    bpy.utils.unregister_class(YNewImageAtlasSegmentTest)
    bpy.utils.unregister_class(YRefreshTransformedLayerUV)
    bpy.utils.unregister_class(YBackToOriginalUV)
    bpy.utils.unregister_class(YImageAtlasSegments)
    bpy.utils.unregister_class(YImageAtlas)
