import shutil
import subprocess
from bpy.types import Context
from .common import * 
from .preferences import * 
from . import lib, Layer, Mask
from bpy.props import *
from bpy.types import PropertyGroup, Panel, Operator, UIList, Scene

import bpy

# export shader, choose location, save file
class ExportShader(Operator):
    """Export to godot shader"""

    bl_label = "Export Shader"
    bl_idname = "godot.export"

    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})

    use_shortcut = True

    temp_godot = "godot4/"

    script_template = '''
shader_type spatial;
{0}vec4 layer(vec4 foreground, vec4 background) {{
    return foreground * foreground.a + background * (1.0 - foreground.a);
}}

void fragment() {{ 
{1}
    ALBEDO = mix_all.rgb;
}}

'''

    script_vars = '''
uniform sampler2D {0};
uniform vec2 {1} = vec2({2},{3}); 
'''
    script_mask_vars = "uniform sampler2D {0};"
    
    script_fragment_var = '''
    vec2 scaled_uv_{0} = UV * {1};
    vec4 albedo_{0} = texture({2}, scaled_uv_{0});'''

    script_mask_fragment_var = '''
    vec4 mask_{0} = texture({1}, UV);
    albedo_{0}.a = mask_{0}.r;
'''

    script_layer_combine_0 = '''

    vec4 mix_all = layer(albedo_0, albedo_1);'''

    script_layer_combine_next = '''
    mix_all = layer(mix_all, albedo_{0});
'''
  #vec4 albedo = texture({1}, scaled_uv_{0});
    
    def execute(self, context):
        node = get_active_ypaint_node()
        yp = node.node_tree.yp

        
        index = 0
        layer:Layer.YLayer

        global_vars = ""
        fragment_vars = ""
        combine_content = ""

        # get directory of filepath
        my_directory = "/home/bocilmania/Documents/projects/blender/ekspor/"
        # addon directory
        addon_dir = os.path.dirname(os.path.realpath(__file__))

        base_arg = ["godot", "--headless", "--path", os.path.join(addon_dir, self.temp_godot)]
        asset_args = []

        if not self.use_shortcut:
            my_directory = os.path.dirname(self.filepath)
            if not os.path.exists(my_directory):
                os.makedirs(my_directory)
        
        for layer in yp.layers:
            if layer.enable:
                mapping = get_layer_mapping(layer)

                layer_var = "layer_"+str(index)

                scale_var = layer_var + "_scale"

                # print("pos", mapping.inputs[1].default_value)
                # print("rot", mapping.inputs[2].default_value)
                # print("scl", mapping.inputs[3].default_value)

                skala = mapping.inputs[3].default_value
                global_vars += self.script_vars.format(layer_var, scale_var, skala.x, skala.y)
                fragment_vars += self.script_fragment_var.format(index, scale_var, layer_var)

                source = get_layer_source(layer)

                image_path = source.image.filepath_from_user()

                asset_args.append(layer_var)
                asset_args.append(bpy.path.basename(image_path))

                # copy to directory 
                print("copy ", image_path, " to ", my_directory)
                shutil.copy(image_path, my_directory)

                # print("filepath ", index, " = ",source.image.filepath_from_user())
                # print("rawpath ", index, " = ",source.image.filepath)
                # print("path user ", index, " = ",source.image.filepath_raw)
                msk:Mask.YLayerMask
                for idx, msk in enumerate(layer.masks):
                    mask_var = layer_var + "_mask_" + str(idx)
                    global_vars += self.script_mask_vars.format(mask_var)
                    fragment_vars += self.script_mask_fragment_var.format(index, mask_var)

                    mask_tree = get_mask_tree(msk)
                    mask_source = mask_tree.nodes.get(msk.source)

                    mask_image_path = mask_source.image.filepath_from_user()

                    if mask_image_path == "":
                        print("unpack item ", msk.name)
                        bpy.ops.file.unpack_item(id_name=msk.name, method='WRITE_ORIGINAL')
                        mask_image_path = mask_source.image.filepath_from_user()
                    else:
                        print("mask path exist ", mask_image_path)

                    asset_args.append(mask_var)
                    asset_args.append(bpy.path.basename(mask_image_path))

                    shutil.copy(mask_image_path, my_directory)
                    print("copy ", mask_image_path, " to ", my_directory)
                global_vars += "\n"

                if index == 1:
                    combine_content += self.script_layer_combine_0
                elif index > 1:
                    combine_content += self.script_layer_combine_next.format(index)
                    
                index += 1

        # print("parameter ", asset_args)
        fragment_vars += combine_content

        content_shader = self.script_template.format(global_vars, fragment_vars)

        # content_shader += self.script_fragment.format(fragment_vars, "coba")
        print(content_shader)

        if self.use_shortcut:
            self.filepath = os.path.join(my_directory, "box.gdshader")

        temp_folder = os.path.join(addon_dir, self.temp_godot, "assets")

        # delete content of temp folder
        for filename in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

        # copy to temp folder
        for filename in os.listdir(my_directory):
            file_path = os.path.join(my_directory, filename)
            shutil.copy(file_path, temp_folder)

        print("addon dir ", addon_dir)

        name_asset = bpy.path.display_name_from_filepath(self.filepath)

        print("file name", name_asset)

        file = open(self.filepath, "w")
        file.write(content_shader)
        file.close()

        all_params = base_arg + ["-s", "scripts/blender_import.gd", "--", name_asset] + asset_args
        print("all params ", all_params)

        print(subprocess.run(base_arg + ["--import"], capture_output=True))
        print(subprocess.run(all_params, capture_output=True))
        print(subprocess.run(base_arg + ["--import"], capture_output=True))

        return {'FINISHED'}

    def invoke(self, context, event):
        if self.use_shortcut:
            return self.execute(context)
        else:
            context.window_manager.fileselect_add(self)
            return {'FINISHED'}
    

classes = [ExportShader]

def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)
    

if __name__ == "__main__":
    register()