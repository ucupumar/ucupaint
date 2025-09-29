import bpy
import os, requests, time, threading, json
from bpy.props import PointerProperty, IntProperty, StringProperty
import bpy.utils.previews
from .common import get_addon_filepath, is_bl_newer_than, is_online, get_addon_title

class YTierPagingButton(bpy.types.Operator):
    """Paging"""
    bl_idname = "wm.y_sponsor_paging"
    bl_label = "Next Page"
    bl_options = {'REGISTER', 'UNDO'}

    is_next_button : bpy.props.BoolProperty(default=True)
    tier_index : bpy.props.IntProperty(default=0)
    max_page : bpy.props.IntProperty(default=0)

    def execute(self, context):
        # print("Paging", "Next" if self.is_next_button else "Previous")
        goal_ui = context.window_manager.ypui_sponsor
        current_page = goal_ui.page_tiers[self.tier_index]
        if self.is_next_button:
            current_page += 1
            if self.max_page > 0 and current_page >= self.max_page:
                current_page = self.max_page - 1
        else:
            current_page -= 1
            if current_page < 0:
                current_page = 0
        goal_ui.page_tiers[self.tier_index] = current_page

        # print("New page for tier", self.tier_index, "=", current_page)
        return {'FINISHED'}

class YSponsorPopover(bpy.types.Panel):
    bl_idname = "NODE_PT_ysponsor_popover"
    bl_label = get_addon_title() + " Sponsor Menu"
    bl_description = get_addon_title() + " Sponsor Menu"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        goal = collaborators.sponsorship_goal
        # one_time_total = 0
        # print("Checking one-time sponsors...", len(collaborators.sponsors))
        # for i in collaborators.sponsors.keys():
        #     sp = collaborators.sponsors[i]
        #     print(i, sp)
        #     if sp["one_time"]:
        #         one_time_total += sp["amount"]
        #         break
        
        # if one_time_total > 0:
        #     layout.label(text=f"One-time sponsors this month: ${one_time_total:.2f}")
        #     layout.separator()
        desc = goal.get('description', '')

        row_quote = layout.row()
        char_per_line = 40
        split_desc = desc.split(' ')
        current_text = '"'
        ucupumar = collaborators.contributors.get('ucupumar', None)
        ucup_icon = ucupumar['thumb'] if ucupumar else 0
        row_quote.template_icon(icon_value = ucup_icon, scale = 3.0)
        col = row_quote.column(align=True)
        for d in split_desc:
            if len(current_text + d) > char_per_line: # rough estimate
                col.label(text=current_text)
                current_text = ''
            current_text += d + ' '
        col.label(text=current_text+"\"")
        col.label(text="~ ucupumar")
        col.separator()

        layout.label(text="The supporters list is updated daily")

class YSponsorProp(bpy.types.PropertyGroup):
    progress : IntProperty(
        default = 0,
        min = 0,
        max = 100,
        description = 'Only counting recurring supporters',
        subtype = 'PERCENTAGE'
    )

    expand_tiers : bpy.props.BoolVectorProperty(
        name = "Expand Tiers",
        description = "Expand Tiers List",
        size = 8, # cannot be dynamic
    )

    page_tiers : bpy.props.IntVectorProperty(
        name = "Page Tiers",
        description = "Page Tiers",
        size = 8, # cannot be dynamic
    )

    expand_description : bpy.props.BoolProperty(
        default = False,
        description = "Ucupaint's sponsor is updated daily",
    )

    initialized : bpy.props.BoolProperty(
        default = False,
    )

    expanded : bpy.props.BoolProperty(
        default = False,
    )

class VIEW3D_PT_YPaint_support_ui(bpy.types.Panel):
    bl_label = "Support " + get_addon_title()
    bl_space_type = 'VIEW_3D'
    #bl_context = "object"
    bl_region_type = 'UI'
    bl_category = get_addon_title()
    bl_options = {'DEFAULT_CLOSED'} 


    def draw_multiline(self, layout, text:str, panel_width:int):
        all_desc = text.split(' ')
        column = layout.column(align=True)
        current_text = ''
        for d in all_desc:
            if len(current_text + d) > panel_width // 15: # rough estimate
                column.label(text=current_text)
                current_text = ''
            current_text += d + ' '
        column.label(text=current_text)

    def draw_expanding_title(self, layout, expand, object, prop_name, title):

        icon = 'DOWNARROW_HLT' if expand else 'RIGHTARROW'
        row = layout.row(align=True)
        rrow = row.row(align=True)

        if is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(object, prop_name, emboss=False, text=title, icon=icon)
        else:
            rrow.prop(object, prop_name, emboss=False, text='', icon=icon)
            rrow.label(text=title)

        return row

    def draw_tier_title(self, layout, expand, object, prop_name, title, index_prop):

        # icons = ['KEYTYPE_KEYFRAME_VEC', 'KEYTYPE_BREAKDOWN_VEC', 'KEYTYPE_JITTER_VEC', 'KEYTYPE_EXTREME_VEC', 'KEYTYPE_MOVING_HOLD_VEC', 'KEYTYPE_GENERATED_VEC']
        if is_bl_newer_than(2, 81):
            icons = ['NODE_SOCKET_OBJECT', 'NODE_SOCKET_FLOAT', 'NODE_SOCKET_RGBA', 'NODE_SOCKET_STRING', 'NODE_SOCKET_BOOLEAN', 'NODE_SOCKET_GEOMETRY']
        else:
            icons = ['KEYTYPE_MOVING_HOLD_VEC']

        icon = 'DOWNARROW_HLT' if expand else 'RIGHTARROW'
        row = layout.row(align=True)
        rrow = row.row(align=True)

        index_icon = index_prop % len(icons)

        if is_bl_newer_than(2, 81):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(object, prop_name, index=index_prop, emboss=False, text='', icon=icon)
            rrow.prop(object, prop_name, index=index_prop, text=title, icon=icons[index_icon], emboss=False)
        elif is_bl_newer_than(2, 80):
            rrow.alignment = 'LEFT'
            rrow.scale_x = 0.95
            rrow.prop(object, prop_name, index=index_prop, emboss=False, text=title, icon=icon)
            # rrow.prop(object, prop_name, index=index_prop, text=title, icon=icons[index_icon], emboss=False)
        else:
            rrow.prop(object, prop_name, index=index_prop, emboss=False, text='', icon=icon)
            # rrow.label(text=title)

        return row

    def draw_header_preset(self, context):
        goal_ui = context.window_manager.ypui_sponsor
        if not goal_ui.expanded:
            layout = self.layout
            row = layout.row(align=True)
            row.operator('wm.url_open', text="Donate Us", icon='FUND').url = "https://github.com/sponsors/ucupumar"
        goal_ui.expanded = False


    def draw_item(self, layout, icon, label, url = '', scale_icon:float = 3.0, horizontal_mode:bool = True):
        if horizontal_mode:
            row = layout.row(align=True)
            row.alignment = 'LEFT'
            if scale_icon != 0.0:
                row.template_icon(icon_value = icon, scale = scale_icon)
                btn_row = row.row(align=True)
                btn_row.scale_y = scale_icon
                btn_url = btn_row.operator('wm.url_open', text=label, emboss=False, )
                btn_url.url = url
            else:
                row.label(text=label)
            
        else:
            col = layout.column(align=True)
            col.template_icon(icon_value = icon, scale = scale_icon)
            col.operator('wm.url_open', text=label, emboss=False).url = url

    def draw_empty_member(self, layout, scale_icon:float = 3.0, horizontal_mode:bool = True):

        content = 'No sponsors yet, be the first one!'
        if horizontal_mode:
            row = layout.row(align=True)
            row.alignment = 'LEFT'
            if scale_icon != 0.0:
                row.template_icon(icon_value = collaborators.empty_pic, scale = scale_icon)
                btn_row = row.row(align=True)
                btn_row.scale_y = scale_icon
                btn_url = btn_row.operator('wm.url_open', text=content, emboss=False, )
                btn_url.url = "https://github.com/sponsors/ucupumar"
            else:
                row.label(text=content)
        else:
            col = layout.column(align=True)
            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.template_icon(icon_value = collaborators.empty_pic, scale = scale_icon)

            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.scale_x = 0.95
            row.operator('wm.url_open', text=content, emboss=False).url = "https://github.com/sponsors/ucupumar"


    def draw_tier_members(self, panel_width, goal_ui, layout, title:str, price, tier_index:int, per_column:int = 3, current_page:int = 0, per_page_item:int = 4, scale_icon:float = 3.0, horizontal_mode:bool = True):
        
        filtered_items = list()

        for item in collaborators.sponsors.values():
            if item['tier'] != tier_index:
                continue
            filtered_items.append(item)

        member_count = len(filtered_items)

        stripped_title = ''.join(c for c in title if ord(c) < 128)
        stripped_title = stripped_title.strip()

        text_object = f'{stripped_title}'
        if member_count > 0:
            text_object += f' ({member_count})'

        expand = goal_ui.expand_tiers[tier_index]
        title_row = self.draw_tier_title(layout, expand, goal_ui, 'expand_tiers', text_object, tier_index)
        paging_layout = title_row.row(align=True)
        paging_layout.alignment = 'RIGHT'

        if per_page_item < per_column:
            per_page_item = per_column

        if expand:
            
            row = layout.row(align=True)
            # col = layout.column(align=True)
            row.label(text='', icon='BLANK1')
            box = row.box()
            if member_count == 0:
                col_box = box.column(align=True)
                # for i in range(per_column):
                self.draw_empty_member(col_box, scale_icon, horizontal_mode)
                # box_row = box.row(align=True)
                # box_row.alignment = 'CENTER'
                # box_row.label(text="No sponsors yet. Be the first one!")
            else:
                lowest_tier = scale_icon == 0.0

                if not lowest_tier:
                    grid = box.grid_flow(row_major=True, columns=per_column, even_columns=True, even_rows=True, align=True)

                missing_column = per_column - (per_page_item % per_column)

                counter_member = 0

                paged_items = filtered_items[current_page * per_page_item : (current_page + 1) * per_page_item]

                lowest_members = ''

                for cl, item in enumerate(paged_items):
                    counter_member += 1
                    thumb = item['thumb']
                    if not thumb:
                        thumb = collaborators.default_pic

                    id = item["name"]
                    if item['one_time']:
                        if horizontal_mode:
                            id +=  "*"
                        else:
                            id =  "*" + id
                    if lowest_tier:
                        lowest_members += id + ', '
                    else:
                        self.draw_item(grid, thumb, id, item["url"], scale_icon, horizontal_mode)
                # if tier_index == 3:
                #     print("Tier", tier_index, "has", member_count, "members", "page", current_page, "per page =", per_page_item, "per column =", per_column, "missing column =", missing_column)
                if lowest_tier and lowest_members != '':
                    lowest_members = lowest_members[:-2] # remove last comma
                    self.draw_multiline(box, lowest_members, panel_width)

                if missing_column != per_column:
                    for i in range(missing_column):
                        self.draw_item(grid, collaborators.default_pic, '', '', scale_icon, horizontal_mode)

            if member_count > per_page_item:

                prev = paging_layout.operator('wm.y_sponsor_paging', text='', icon='TRIA_LEFT')
                prev.is_next_button = False
                prev.tier_index = tier_index
                prev.max_page = (member_count + per_page_item - 1) // per_page_item

                paging_layout.label(text=f"{current_page + 1}/{prev.max_page}")

                next = paging_layout.operator('wm.y_sponsor_paging', text='', icon='TRIA_RIGHT')
                next.is_next_button = True
                next.tier_index = tier_index
                next.max_page = prev.max_page
                
        # paging_layout.separator()
        # paging_layout.popover("NODE_PT_ysponsor_popover", text='', icon='INFO')

    def draw(self, context):

        region = context.region
        panel_width = region.width

        layout = self.layout
        goal = collaborators.sponsorship_goal
        goal_ui = context.window_manager.ypui_sponsor

        if is_online() and goal and 'targetValue' in goal:
           
            row_title = layout.row(align=True)
            row_title.label(text="Ucupaint's goal : $" + str(goal['targetValue']) + "/month")

            paging_layout = row_title.row(align=True)
            paging_layout.alignment = 'RIGHT'
            paging_layout.popover("NODE_PT_ysponsor_popover", text='', icon='QUESTION')
            
            target = goal['targetValue']
            percentage = goal['percentComplete']
            donation = target * percentage / 100
        
            goal_ui.progress = goal['percentComplete']
            layout.prop(goal_ui, 'progress', text=f"${donation}", slider=True)
            

        don_col = layout.column(align=True)
        don_col.scale_y = 1.5
        don_col.operator('wm.url_open', text="Donate Us", icon='FUND').url = "https://github.com/sponsors/ucupumar"

        check_contributors(context)

        if is_online():
            layout.separator()
            layout.label(text="Our Supporters :", icon='HEART')

            tiers:list = goal.get('tiers', [])
            if tiers:
                for tier in reversed(tiers):
                    idx = tiers.index(tier)

                    scale_icon = tier.get('scale', 3)
                    horizontal_mode = tier.get('horizontal', True)
                    per_column_width = tier.get('per_item_width', 200)

                    column_count = panel_width // per_column_width
                    if column_count <= 0:
                        column_count = 1

                    self.draw_tier_members(panel_width, goal_ui, layout, tier['name'], tier['price'], idx, column_count, goal_ui.page_tiers[idx], tier['per_page_item'], scale_icon, horizontal_mode)

            # check one time sponsor exist and expanded
            for item in collaborators.sponsors.values():
                if item['one_time']:
                    tier = item['tier']
                    if goal_ui.expand_tiers[tier]:
                        layout.separator()
                        layout.label(text="* One-time supporters")
                        break
        else:
            layout.label(text="No internet access, can't load sponsors.", icon='ERROR')
            # open online access 

        goal_ui.expanded = True



# todo :
# settingan per tier (mode, show default, scale icon, width_size)
# column di horizontal mode
# bug dummy items
# info : update per hari
# UCUPAINt goal description dropdown

# cari : View lock di View
# 2 teratas tier with member > expand  
# icon tier
# override user
# max user visible per tier
# paging per tier
# tombol info per tier

# [your name] here, empty tier
# include one time 

# blender 2.8
# link empty
# title : supporters
# panah kurus + icon 
# one time sponsor legend (only if one time exist)

# description, update daily, one time ditaruh di [?]
# one time, --> check visible one time member

# paging contributors

def load_preview(key:str, file_name:str):
    if key in previews_users:
        img = previews_users[key]
    else:
        img = previews_users.load(key, file_name, 'IMAGE', True)
    return img

def check_contributors(context):
    goal_ui = context.window_manager.ypui_sponsor
    if not goal_ui.initialized: # first time init
        goal_ui.initialized = True
        print("first time init, loading contributors...")
        load_contributors()

        expanding_top_tier = 2 # todo : from settings
        # tier setup
        tiers = collaborators.sponsorship_goal.get('tiers', [])

        # reset expand
        for i in goal_ui.expand_tiers:
            i = False

        total_tiers = len(tiers)
        for idx in range(total_tiers):
            i = total_tiers - 1 - idx
            if expanding_top_tier > 0:
                # check member count 
                member_count = 0
                for item in collaborators.sponsors.values():
                    if item['tier'] == i:
                        member_count += 1
                if member_count > 0:
                    goal_ui.expand_tiers[i] = True
                    expanding_top_tier -= 1

def load_contributors():    

    reload_contributors = False
    path = get_addon_filepath()
    path_last_check = os.path.join(path, "last_check.txt") # to store last check time

    current_time = time.time()

    if os.path.exists(path_last_check):
        with open(path_last_check, "r", encoding="utf-8") as f:
            content_last_check = f.read().strip()
            
            # convert to float
            try:
                last_check = float(content_last_check)
            except:
                last_check = 0.0
            

            span_time = current_time - last_check
            # if last check more than a day ago, reload
            if span_time > 24 * 60 * 60:
                reload_contributors = True
            else:
                # format span in hours
                span_hours = span_time / 3600
                format_last_check = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_check))
                print(f"Last check was {span_hours:.2f} hours ago. Checked at {format_last_check}. Not reloading contributors.")
    else:
        reload_contributors = True       


    path_contributors = os.path.join(path, "contributors.csv")
    content = ""

    # read file if exists
    if os.path.exists(path_contributors):
        with open(path_contributors, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        reload_contributors = True

    path_sponsors = os.path.join(path, "sponsors.csv")
    content_sponsors = ""

    if os.path.exists(path_sponsors):
        with open(path_sponsors, "r", encoding="utf-8") as f:
            content_sponsors = f.read()
    else:
        reload_contributors = True

    path_sponsorship_goal = os.path.join(path, "sponsorship-goal.json")
    content_sponsorship_goal = ""

    if os.path.exists(path_sponsorship_goal):
        with open(path_sponsorship_goal, "r", encoding="utf-8") as f:
            content_sponsorship_goal = f.read()
            collaborators.sponsorship_goal = json.loads(content_sponsorship_goal)
    else:
        reload_contributors = True

    if reload_contributors and is_online():

        data_url = "https://raw.githubusercontent.com/ucupumar/ucupaint-wiki/master/data/"
        try:
            print("Reloading contributors...")
            response = requests.get(data_url + "contributors.csv", verify=False, timeout=10)
            if response.status_code == 200:
                content = response.text
                print("Response:", content)

                with open(path_contributors, "w", encoding="utf-8") as f:
                    f.write(content)

            print("Reloading sponsors...")
            response = requests.get(data_url + "sponsors.csv", verify=False, timeout=10)
            if response.status_code == 200:
                content_sponsors = response.text
                print("Response:", content_sponsors)
                with open(path_sponsors, "w", encoding="utf-8") as f:
                    f.write(content_sponsors)

            print("Reloading sponsorship goal...", data_url + "sponsorship-goal.json")
            response = requests.get(data_url + "sponsorship-goal.json", verify=False, timeout=10)
            if response.status_code == 200:
                content_sponsorship_goal = response.text
                print("Response:", content_sponsorship_goal)
                with open(path_sponsorship_goal, "w", encoding="utf-8") as f:
                    f.write(content_sponsorship_goal)
                collaborators.sponsorship_goal = json.loads(content_sponsorship_goal)

            current_time = time.time()
            with open(path_last_check, "w", encoding="utf-8") as f:
                f.write(str(current_time))

        except requests.exceptions.ReadTimeout:
            reload_contributors = False
    else:
        reload_contributors = False


    collaborators.contributors.clear()
    for line in content.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3:
            contributor = {
                'id': parts[0],
                'url': parts[1],
                'image_url': parts[2],
                'thumb': None
            }
            collaborators.contributors[contributor['id']] = contributor

    folders = os.path.join(path, "icons", "contributors")
    if not os.path.exists(folders):
        os.makedirs(folders)

    collaborators.sponsors.clear()
    for line in content_sponsors.strip().splitlines():
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 6:
            sponsor = {
                'id': parts[0],
                'name': parts[1],
                'url': parts[2],
                'image_url': parts[3],
                'amount': float(parts[5]) if parts[5] != '' else 0.0,
                'one_time' : parts[6] == 'True',
                'tier': int(parts[7]),
                
                'thumb': None
            }
            collaborators.sponsors[sponsor['id']] = sponsor

    # retrieve images

    icon_size = 512

    # Download contributor images
    links = [c['image_url']+f"&s={icon_size}" for c in collaborators.contributors.values()]
    file_names = [f"{folders}{os.sep}{c['id']}.png" for c in collaborators.contributors.values()]
    ids = [c['id'] for c in collaborators.contributors.values()]

    # check images exist
    for file_name in file_names:
        if not os.path.exists(file_name):
            reload_contributors = True
            break

    # Download sponsor images
    links_sponsors = [c['image_url']+f"&s={icon_size}" for c in collaborators.sponsors.values()]
    file_names_sponsors = [f"{folders}{os.sep}{c['id']}.png" for c in collaborators.sponsors.values()]
    ids_sponsors = [c['id'] for c in collaborators.sponsors.values()]

    # check images exist
    for file_name in file_names_sponsors:
        if not os.path.exists(file_name):
            reload_contributors = True
            break

    if reload_contributors:
        # remove all images in folder 
        for f in os.listdir(folders):
            file_path = os.path.join(folders, f)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print("Error removing file", file_path, ":", e)

        new_thread = threading.Thread(target=download_stream, args=(links,file_names,ids, collaborators.contributors))
        new_thread.start()

        new_thread_sponsors = threading.Thread(target=download_stream, args=(links_sponsors,file_names_sponsors,ids_sponsors, collaborators.sponsors))
        new_thread_sponsors.start()
    else:
        for idx, file_name in enumerate(file_names):
            k = ids[idx]
            if os.path.exists(file_name):
                img = load_preview(k, file_name)
                collaborators.contributors[k]['thumb'] = img.icon_id
                # print("loaded contributor ", k, " = ", collaborators.contributors[k])
            else:
                print("file not found", file_name)

        for idx, file_name in enumerate(file_names_sponsors):
            k = ids_sponsors[idx]
            if os.path.exists(file_name):
                img = load_preview(k, file_name)
                collaborators.sponsors[k]['thumb'] = img.icon_id
                # print("loaded sponsor ", k, " = ", collaborators.sponsors[k])
            else:
                print("file not found", file_name)

    # extra dummy
    show_extra_dummy = False
    empty_all_sponsors = False

    if show_extra_dummy:
        tiers = collaborators.sponsorship_goal.get('tiers', [])
        tier_count = len(tiers)

        dummy_multiplier = 3

        for m in range(dummy_multiplier):
            for i, contributor in enumerate(collaborators.contributors.values()):
                random_num = hash(contributor['id']) % 1000

                new_contributor = contributor.copy()

                new_contributor['tier'] = i % tier_count
                new_contributor['one_time'] = True if (random_num % 2) == 0 else False

                if m == 0:
                    new_contributor['name'] = contributor['id']
                    collaborators.sponsors[contributor['id']] = new_contributor
                else:
                    new_contributor['name'] = contributor['id'] + str(m)
                    collaborators.sponsors[contributor['id']+str(m)] = new_contributor

                print(new_contributor)
    elif empty_all_sponsors:
        collaborators.sponsors.clear()

def download_stream(links, file_names, ids, dict, timeout:int = 10):
    for idx, file_name in enumerate(file_names):
        link = links[idx]
        print("Downloading", link, "to", file_name)
        with open(file_name, "wb") as f:
            try:
                response = requests.get(link, stream=True, timeout = timeout)
                total_length = response.headers.get('content-length')
                print("total size = "+total_length)
                if not total_length:
                    print('Error #1 while downloading', link, ':', "Empty Response.")
                    return
                
                dl = 0
                total_length = int(total_length)
                # TODO a way for calculating the chunk size
                for data in response.iter_content(chunk_size = 4096):

                    dl += len(data)
                    f.write(data)
            except Exception as e:
                print('Error #2 while downloading', link, ':', e)

        k = ids[idx]
        img = load_preview(k, file_name)
        dict[k]['thumb'] = img.icon_id
        print("loaded", k, " = ", dict[k])

classes = [
    VIEW3D_PT_YPaint_support_ui,
    YSponsorProp,
    YTierPagingButton,
    YSponsorPopover
]

class Collaborators:
    default_pic = None
    empty_pic = None
    contributors = {}
    sponsors = {}
    sponsorship_goal = {}

def get_collaborators():
    return collaborators

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    global previews_users
    global collaborators

    collaborators = Collaborators()

    previews_users = bpy.utils.previews.new()

    blank_path = os.path.join(get_addon_filepath(), "icons", "blank.png")
    blank_img = load_preview('blank', blank_path)
    collaborators.default_pic = blank_img.icon_id

    empty_path = os.path.join(get_addon_filepath(), "icons", "empty.png")
    empty_img = load_preview('empty', empty_path)
    collaborators.empty_pic = empty_img.icon_id

    collaborators.contributors = {}
    collaborators.sponsors = {}
    collaborators.sponsorship_goal = {}

    bpy.types.WindowManager.ypui_sponsor = PointerProperty(type=YSponsorProp)

    ui_sp = bpy.context.window_manager.ypui_sponsor
    ui_sp.initialized = False

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.WindowManager.ypui_sponsor

    global previews_users

    bpy.utils.previews.remove(previews_users)
    previews_users = None

