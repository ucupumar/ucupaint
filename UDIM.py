import bpy, numpy, os, tempfile
from bpy.props import *
from .common import *

UDIM_DIR = 'UDIM__'
UV_TOLERANCE = 0.1

def is_udim_supported():
    return is_greater_than_340()

def fill_tiles(image, color, width=0, height=0, empty_only=False):
    if image.source != 'TILED': return
    for tile in image.tiles:
        fill_tile(image, tile.number, color, width, height, empty_only)

def fill_tile(image, tilenum, color, width=0, height=0, empty_only=False):
    if image.source != 'TILED': return
    tile = image.tiles.get(tilenum)
    new_tile = False
    if not tile:
        tile = image.tiles.new(tile_number=tilenum)
        new_tile = True

    if tile.size[0] == 0 or tile.size[1] == 0:
        new_tile = True

    image.tiles.active = tile

    if not new_tile and empty_only: return

    if width == 0: width = tile.size[0]
    if height == 0: height = tile.size[1]
    if width == 0: width = 1024
    if height == 0: height = 1024

    # NOTE: Override operator won't work on Blender 4.0
    #override = bpy.context.copy()
    #override['edit_image'] = image
    #bpy.ops.image.tile_fill(override, color=color, width=width, height=height, float=image.is_float, alpha=True)

    # Fill tile
    ori_ui_type = bpy.context.area.ui_type
    bpy.context.area.ui_type = 'IMAGE_EDITOR'
    bpy.context.space_data.image = image
    bpy.ops.image.tile_fill(color=color, width=width, height=height, float=image.is_float, alpha=True)
    bpy.context.area.ui_type = ori_ui_type

def copy_udim_pixels(src, dest):
    for tile in src.tiles:
        # Check if tile number exists on both images and has same sizes
        dtile = dest.tiles.get(tile.number)
        if not dtile: continue
        if tile.size[0] != dtile.size[0] or tile.size[1] != dtile.size[1]: continue

        # Swap first
        if tile.number != 1001:
            swap_tile(src, 1001, tile.number)
            swap_tile(dest, 1001, tile.number)

        # Set pixels
        dst.pixels = list(src.pixels)

        # Swap back
        if tile.number != 1001:
            swap_tile(src, 1001, tile.number)
            swap_tile(dest, 1001, tile.number)

def get_tile_numbers(objs, uv_name):

    if not is_udim_supported(): return [1001]

    T = time.time()

    # Get active object
    obj = bpy.context.object
    ori_mode = 'OBJECT'
    if obj in objs and obj.mode != 'OBJECT':
        ori_mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    arr = numpy.empty(0, dtype=numpy.float32)

    # Get all uv coordinates
    for o in objs:
        uv = o.data.uv_layers.get(uv_name)
        if not uv: continue
    
        uv_arr = numpy.zeros(len(o.data.loops)*2, dtype=numpy.float32)
        uv.data.foreach_get('uv', uv_arr)
        arr = numpy.append(arr, uv_arr)

    # Reshape the array to 2D
    arr.shape = (arr.shape[0]//2, 2)

    # Tolerance to skip value around x.0
    trange = [UV_TOLERANCE/2.0, 1.0-(UV_TOLERANCE/2.0)]
    arr = arr[((arr[:,0]-(numpy.floor(arr[:,0]))) >= trange[0]) &
              ((arr[:,0]-(numpy.floor(arr[:,0]))) <= trange[1]) & 
              ((arr[:,1]-(numpy.floor(arr[:,1]))) >= trange[0]) &
              ((arr[:,1]-(numpy.floor(arr[:,1]))) <= trange[1])]

    # Floor array to integer
    arr = numpy.floor(arr).astype(int)

    # Get unique value only
    arr = numpy.unique(arr, axis=0)
    
    # Get the udim representation
    tiles = []
    for i in arr:

        # UV value can only be within 0 .. 10 range
        u = min(max(i[0], 0), 10)
        v = min(max(i[1], 0), 10)

        # Calculate the tile
        tile = 1001 + u + v*10
        if tile not in tiles:
            tiles.append(tile)
    
    if ori_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=ori_mode)

    print('INFO: Getting tile numbers are done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')
        
    return tiles

def is_uvmap_udim(objs, uv_name):

    if not is_udim_supported(): return False

    T = time.time()

    # Get active object
    obj = bpy.context.object
    ori_mode = 'OBJECT'
    if obj in objs and obj.mode != 'OBJECT':
        ori_mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    arr = numpy.empty(0, dtype=numpy.float32)

    # Get all uv coordinates
    for o in objs:
        uv = o.data.uv_layers.get(uv_name)
        if not uv: continue
    
        uv_arr = numpy.zeros(len(o.data.loops)*2, dtype=numpy.float32)
        uv.data.foreach_get('uv', uv_arr)
        arr = numpy.append(arr, uv_arr)

    if ori_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=ori_mode)

    is_udim = numpy.any(arr > 1.0 + UV_TOLERANCE/2)

    print('INFO: UDIM checking is done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

    return is_udim

def get_temp_udim_dir():
    if bpy.data.filepath != '':
        directory = os.path.dirname(bpy.data.filepath)
        return os.path.join(directory, UDIM_DIR)

    return tempfile.gettempdir()

def is_using_temp_dir(image):
    directory = os.path.dirname(bpy.path.abspath(image.filepath))
    if directory == get_temp_udim_dir() or directory == tempfile.gettempdir():
        return True
    return False

def remove_udim_files_from_disk(image, directory, remove_dir=False):
    # Get filenames
    img_names = []
    filename = bpy.path.basename(image.filepath)
    prefix = filename.split('.<UDIM>.')[0]
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            m = re.match(r'' + re.escape(prefix) + '\.\d{4}\.*', f)
            if m: img_names.append(f)

    # Remove images
    for f in img_names:
        try: os.remove(os.path.join(directory, f))
        except Exception as e: print(e)

    # Remove directory
    if remove_dir and directory != tempfile.gettempdir():
        try: os.rmdir(directory)
        except Exception as e: print(e)

def set_udim_filepath(image, filename, directory):
    filepath = os.path.join(directory, filename + '.<UDIM>.png')
    if directory != tempfile.gettempdir():
        try: image.filepath = bpy.path.relpath(filepath)
        except: image.filepath = filepath
    else: image.filepath = filepath

def is_image_filepath_unique(image):
    for img in bpy.data.images:
        if img != image and img.filepath == image.filepath:
            return False
    return True

# UDIM need filepath to work, 
# So there's need to initialize filepath for every udim image created
def initial_pack_udim(image, base_color=None, filename=''):

    # Get temporary directory
    temp_dir = get_temp_udim_dir()

    # Check if image is already packed
    use_packed = False 
    if image.packed_file: use_packed = True

    # Check if image already use temporary filepath
    use_temp_dir = is_using_temp_dir(image)

    # Set temporary filepath
    if (image.filepath == '' or # Set image filepath if it's still empty
        not is_image_filepath_unique(image) # Force set new filepath when image filepath is not unique
        ):
        use_temp_dir = True
        filename = filename if filename != '' else image.name
        set_udim_filepath(image, filename, temp_dir)

    # When blend file is copied to another PC, there's a chance directory is missing
    directory = os.path.dirname(bpy.path.abspath(image.filepath))
    if not use_temp_dir and not os.path.isdir(directory):
        ori_ui_type = bpy.context.area.ui_type
        bpy.context.area.ui_type = 'IMAGE_EDITOR'
        bpy.context.space_data.image = image
        path = temp_dir + os.sep + image.name + '.<UDIM>.png'
        bpy.ops.image.save_as(filepath=path , relative_path=True)
        bpy.context.area.ui_type = ori_ui_type
        use_temp_dir = True

    # Save then pack
    image.save()
    if use_packed or use_temp_dir:
        image.pack()

    # Remove temporary files
    if use_temp_dir:
        remove_udim_files_from_disk(image, temp_dir, True)

    # Remember base color
    if base_color:
        image.yui.base_color = base_color

def swap_tile(image, tilenum0, tilenum1):

    tile0 = image.tiles.get(tilenum0)
    tile1 = image.tiles.get(tilenum1)

    if not tile0 or not tile1: return

    str0 = '.' + str(tilenum0) + '.'
    str1 = '.' + str(tilenum1) + '.'
    filename = bpy.path.basename(image.filepath)
    prefix = filename.split('.<UDIM>.')[0]
    directory = os.path.dirname(bpy.path.abspath(image.filepath))

    # Remember stuff
    ori_packed = False
    if image.packed_file: ori_packed = True

    # Save the image first
    image.save()

    # Get image paths
    path0 = ''
    path1 = ''
    for f in os.listdir(directory):
        m = re.match(r'' + re.escape(prefix) + '\.\d{4}\.*', f)
        if m:
            if str0 in f: path0 = os.path.join(directory, f)
            elif str1 in f: path1 = os.path.join(directory, f)
    
    # Swap paths
    temp_path = path0.replace(str0, '.xxxx.')
    os.rename(path0, temp_path)
    os.rename(path1, path0)
    os.rename(temp_path, path1)
    
    # Reload to update image
    image.reload()

    # Repack image
    if ori_packed:
        image.pack()

        # Remove file if they are using temporary directory
        if is_using_temp_dir(image):
            remove_udim_files_from_disk(image, directory, True)

class YRefillUDIMTiles(bpy.types.Operator):
    bl_idname = "node.y_refill_udim_tiles"
    bl_label = "Refill UDIM Tiles"
    bl_description = "Refill all UDIM tiles used by all layers and masks based on their UV"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        yp = context.layer.id_data.yp
        entities, images, segments = get_yp_entities_images_and_segments(yp)

        mat = get_active_material()

        for i, image in enumerate(images):
            if image.source != 'TILED': continue
            ents = entities[i]
            entity = ents[0]

            # Get width and height
            width = 1024
            height = 1024
            if image.size[0] != 0: width = image.size[0]
            if image.size[1] != 0: height = image.size[1]

            # Get tile numbers based from uv
            uv_name = entity.uv_name
            objs = get_all_objects_with_same_materials(mat, True, uv_name)
            tilenums = get_tile_numbers(objs, uv_name)

            color = image.yui.base_color

            for tilenum in tilenums:
                fill_tile(image, tilenum, color, width, height, empty_only=True)

            initial_pack_udim(image)

        return {'FINISHED'}

class YUDIMAtlasSegments(bpy.types.PropertyGroup):

    name : StringProperty(
            name='Name',
            description='Name of UDIM Atlas Segments',
            default='')

    y_offset : IntProperty(default=0)

    #tile_x : IntProperty(default=0)
    #tile_y : IntProperty(default=0)

    #width : IntProperty(default=1024)
    #height : IntProperty(default=1024)

    #unused : BoolProperty(default=False)

    #bake_info : PointerProperty(type=BakeInfo.YBakeInfoProps)

class YUDIMAtlas(bpy.types.PropertyGroup):
    name : StringProperty(
            name='Name',
            description='Name of UDIM Atlas',
            default='')

    is_udim_atlas : BoolProperty(default=False)

    #color : EnumProperty(
    #        name = 'Atlas Base Color',
    #        items = (('WHITE', 'White', ''),
    #                 ('BLACK', 'Black', ''),
    #                 ('TRANSPARENT', 'Transparent', '')),
    #        default = 'BLACK')

    #float_buffer : BoolProperty(default=False)
    step_y : IntProperty(default=1, min=1, max=9)

    segments : CollectionProperty(type=YUDIMAtlasSegments)

class YUDIMInfo(bpy.types.PropertyGroup):
    base_color : FloatVectorProperty(subtype='COLOR', size=4, min=0.0, max=1.0, default=(0.0, 0.0, 0.0, 0.0))

def register():
    bpy.utils.register_class(YRefillUDIMTiles)
    bpy.utils.register_class(YUDIMAtlasSegments)
    bpy.utils.register_class(YUDIMAtlas)
    bpy.utils.register_class(YUDIMInfo)

    #bpy.types.Image.yua = PointerProperty(type=YUDIMAtlas)
    bpy.types.Image.yui = PointerProperty(type=YUDIMInfo)

def unregister():
    bpy.utils.unregister_class(YRefillUDIMTiles)
    bpy.utils.unregister_class(YUDIMAtlasSegments)
    bpy.utils.unregister_class(YUDIMAtlas)
    bpy.utils.unregister_class(YUDIMInfo)
