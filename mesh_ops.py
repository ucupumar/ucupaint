import bpy, bmesh
from collections import defaultdict
from mathutils import Vector, Matrix
from math import *
import numpy as np

STD_DEV = 2

def get_list_of_uv_islands(obj, uv_name = ''):
    scene = bpy.context.scene

    if obj.type != 'MESH': return
    if obj.name not in scene.objects: return
    if len(obj.data.uv_layers) == 0: return

    # Prepare active object and uv
    bpy.ops.object.mode_set(mode='OBJECT')

    for o in scene.objects:
        o.select = False

    scene.objects.active = obj
    obj.select = True

    if uv_name != '':

        if hasattr(obj.data, 'uv_textures'):
            uv_layers = obj.data.uv_textures
        else: uv_layers = obj.data.uv_layers

        for uv in obj.data.uv_layers:
            if uv.name == uv_name:
                obj.data.uv_layers.active = True
                break

    # Go to edit mode to access bmesh data
    bpy.ops.object.mode_set(mode='EDIT')

    __face_to_verts = defaultdict(set)
    __vert_to_faces = defaultdict(set)
    
    bm = bmesh.from_edit_mesh(obj.data)
    #bm.verts.ensure_lookup_table()
    #bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()

    for f in bm.faces:
        for l in f.loops:
            id = l[uv_layer].uv.to_tuple(5), l.vert.index
            __face_to_verts[f.index].add(id)
            __vert_to_faces[id].add(f.index)

    def __parse_island(bm, face_idx, faces_left, island):
        if face_idx in faces_left:
            faces_left.remove(face_idx)
            #island.append({'face': bm.faces[face_idx]})
            #island.append(bm.faces[face_idx])
            island.append(face_idx)
            for v in __face_to_verts[face_idx]:
                connected_faces = __vert_to_faces[v]
                if connected_faces:
                    for cf in connected_faces:
                        __parse_island(bm, cf, faces_left, island)
    
    def __get_island(bm):
        uv_island_lists = []
        faces_left = set(__face_to_verts.keys())
        while len(faces_left) > 0:
            current_island = []
            face_idx = list(faces_left)[0]
            __parse_island(bm, face_idx, faces_left, current_island)
            uv_island_lists.append(current_island)
        return uv_island_lists

    uv_island_lists = __get_island(bm)
    
    bpy.ops.object.mode_set(mode='OBJECT')

    return uv_island_lists

def get_polygon_tris_dict(mesh):

    mesh.update(calc_tessface=True)

    poltris = defaultdict(list)

    tessfaces = [tf for tf in mesh.tessfaces]

    for i, p in enumerate(mesh.polygons):

        already_tracer = []

        for j, tf in enumerate(tessfaces):

            tri_0 = [tf.vertices[0], tf.vertices[1], tf.vertices[2]]
            if len(tf.vertices) == 4:
                tri_1 = [tf.vertices[0], tf.vertices[2], tf.vertices[3]]
            else: tri_1 = []

            if set(tri_0) <= set(p.vertices) and (not tri_1 or set(tri_1) <= set(p.vertices)):
                poltris[i].append(tri_0)
                if tri_1: poltris[i].append(tri_1)

                already_tracer.append(j)

                if len(p.vertices) in {3,4} and len(already_tracer) == 1: break

        #print(i, list(reversed(already_tracer)), len(tessfaces))

        for j in reversed(already_tracer):
            del tessfaces[j]

    return poltris

def create_face(mesh, v0, v1, v2):
    
    p = len(mesh.polygons)
    l = len(mesh.loops)

    mesh.polygons.add(1)
    mesh.loops.add(3)
    
    pol = mesh.polygons[p]
    pol.loop_start = l
    pol.loop_total = 3
    pol.vertices = [v0, v1, v2]
    
    mesh.loops[l].vertex_index = v0
    mesh.loops[l+1].vertex_index = v1
    mesh.loops[l+2].vertex_index = v2

def debug_mesh_tris(scene, obj, poltris):
    # New mesh
    mesh = bpy.data.meshes.new("Tessface Cache")

    mesh.vertices.add(len(obj.data.vertices))
    verts = []
    for v in obj.data.vertices:
        verts.extend(v.co)
    mesh.vertices.foreach_set("co", verts)

    for key, val in poltris.items():
        for v in val:
            create_face(mesh, v[0], v[1], v[2])

    mesh.validate()
    mesh.update()
    
    o = bpy.data.objects.new("Tessfaces Copy", mesh)
    o.matrix_world = obj.matrix_world
    o.draw_type = 'WIRE'
    o.show_x_ray = True

    scene.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT')
    o.select = True
    scene.objects.active = o
    scene.update()

def get_tangent_and_bitangent(v_0, v_1, v_2, uv_0, uv_1, uv_2):

    v0 = v_0.co.copy()
    v1 = v_1.co.copy()
    v2 = v_2.co.copy()
    
    v1 = v1 - v0
    v2 = v2 - v0
    
    uv0 = uv_0.uv.copy()
    uv1 = uv_1.uv.copy()
    uv2 = uv_2.uv.copy()

    #print(uv0, uv1, uv2, loop_0, loop_1, loop_2)

    uv1 = uv1 - uv0
    uv2 = uv2 - uv0
    
    det = uv1.x*uv2.y - uv2.x*uv1.y
    #print(uv0, uv1, uv2, det)

    if abs(det) < 0.0001:
        return Vector((0,0,0)), Vector((0,0,0))

    T = (uv2.y * v1 - uv1.y  * v2) / det 
    #B = (-uv2.x * v1 - uv1.x * v2) / det
    B = (uv1.x * v2 - uv2.x * v1) / det

    return T.normalized(), B.normalized()
    #return T, B

def avg_vec3(vecs):
    sum_vec = Vector((0, 0, 0))
    for v in vecs:
        sum_vec += v

    return sum_vec / len(vecs)

def zip_island_vectors(combined, vectors):

    # Get means and standard deviation of all the values
    combined = np.array(combined)
    mean = np.mean(combined, axis=0)
    sd = np.std(combined, axis=0)

    # To store outlier vectors
    outliers = {}
    num_outliers = 0

    # To store minimum and maximum value
    #min_val = 0.0
    #max_val = 0.0
    min_val = combined[0] if any(combined) else 0.0
    max_val = combined[0] if any(combined) else 0.0

    for i, ps in vectors.items():
        outliers[i] = {}
        for j, v in ps.items():
            # Flag for Min x Min y Max x Max y outliers
            outliers[i][j] = [False, False, False, False]
            vector = Vector((v[0], v[1]))

            if vector.x < mean - STD_DEV * sd:
                outliers[i][j][0] = True
                num_outliers += 1
            elif vector.x < min_val:
                min_val = vector.x

            if vector.y < mean - STD_DEV * sd:
                outliers[i][j][1] = True
                num_outliers += 1
            elif vector.y < min_val:
                min_val = vector.y

            if vector.x > mean + STD_DEV * sd:
                outliers[i][j][2] = True
                num_outliers += 1
            elif vector.x > max_val:
                max_val = vector.x

            if vector.y > mean + STD_DEV * sd:
                outliers[i][j][3] = True
                num_outliers += 1
            elif vector.y > max_val:
                max_val = vector.y

    span = abs(max_val - min_val)

    if span < 0.0001:
        return 0.0, 1.0, vectors

    scaled_vectors = {}

    for i, vs in vectors.items():
        scaled_vectors[i] = {}
        for j, v in vs.items():
            vector = Vector((v[0], v[1]))

            scaled_vector = (vector - Vector((min_val, min_val))) / span
            outlier = False

            if outliers[i][j][0]:
                scaled_vector.x = 0.0
                outlier = True

            if outliers[i][j][1]:
                scaled_vector.y = 0.0
                outlier = True

            if outliers[i][j][2]:
                scaled_vector.x = 1.0
                outlier = True

            if outliers[i][j][3]:
                scaled_vector.y = 1.0
                outlier = True

            #if outlier:
            #   print(j, scaled_vector)

            scaled_vectors[i][j] = scaled_vector

    #print(min_val, max_val)
    #print(mean, sd, 1-num_outliers/len(combined))

    return min_val, span, scaled_vectors

def get_uv_scale_factor(mesh, uv_islands):

    uv_layer = mesh.uv_layers.active.data

    scales = {}

    combined = []

    for i, pols in enumerate(uv_islands):

        scales[i] = defaultdict(list)

        for p in pols:
            pol = mesh.polygons[p]

            v0 = mesh.vertices[pol.vertices[0]].co.copy()
            v1 = mesh.vertices[pol.vertices[1]].co.copy()
            v2 = mesh.vertices[pol.vertices[2]].co.copy()

            # Get delta vertex coordinates
            v1 = v1 - v0
            v2 = v2 - v0

            loop_0 = pol.loop_indices[0]
            loop_1 = pol.loop_indices[1]
            loop_2 = pol.loop_indices[2]

            loop0 = mesh.loops[loop_0]
            loop1 = mesh.loops[loop_1]
            loop2 = mesh.loops[loop_2]

            # Get uv coordinate
            uv0 = uv_layer[loop_0].uv.copy()
            uv1 = uv_layer[loop_1].uv.copy()
            uv2 = uv_layer[loop_2].uv.copy()

            # Get delta uv
            uv1 = uv1 - uv0
            uv2 = uv2 - uv0

            scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop0, v1, v2, uv1, uv2)

            #if scale_x < 0 or scale_y < 0:
            #    print(p, scale_x, scale_y)

            #if scale_x < 0 or scale_y < 0:
            #    scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop1, v1, v2, uv1, uv2)

            #if scale_x < 0 or scale_y < 0:
            #    scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop2, v1, v2, uv1, uv2)

            scale = Vector((scale_x, scale_y))

            #print(p, scale)

            scales[i][p] = scale
            combined.append(scale_x)
            combined.append(scale_y)

    min_val, span, scaled_scales = zip_island_vectors(combined, scales)

    return min_val, span, scaled_scales

def get_manual_tangent_bitangents(mesh, uv_islands, poltris):

    verts = mesh.vertices
    uv_layer = mesh.uv_layers.active.data

    raw_tangents = defaultdict(dict)
    raw_bitangents = defaultdict(dict)

    # Get tangent for each vertex
    for i, uvi in enumerate(uv_islands):

        for p in uvi:
            pol = mesh.polygons[p]

            #for v in pol.vertices:
            #    if v not in raw_tangents[i]:
            #        raw_tangents[i][v] = []
            #    if v not in raw_bitangents[i]:
            #        raw_bitangents[i][v] = []

            for tri in poltris[p]:

                v_0 = verts[tri[0]]
                v_1 = verts[tri[1]]
                v_2 = verts[tri[2]]

                loop_0 = [li for li in pol.loop_indices if mesh.loops[li].vertex_index == tri[0]][0]
                loop_1 = [li for li in pol.loop_indices if mesh.loops[li].vertex_index == tri[1]][0]
                loop_2 = [li for li in pol.loop_indices if mesh.loops[li].vertex_index == tri[2]][0]

                uv_0 = uv_layer[loop_0]
                uv_1 = uv_layer[loop_1]
                uv_2 = uv_layer[loop_2]

                #print()

                T, B = get_tangent_and_bitangent(v_0, v_1, v_2, uv_0, uv_1, uv_2)
                #print(T,B)
                #raw_tangents[i][tri[0]].append(T)
                #raw_bitangents[i][tri[0]].append(B)

                #T, B = get_tangent_and_bitangent(v_1, v_2, v_0, uv_1, uv_2, uv_0)
                #print(T,B)
                #raw_tangents[i][tri[1]].append(T)
                #raw_bitangents[i][tri[1]].append(B)

                #T, B = get_tangent_and_bitangent(v_2, v_0, v_1, uv_2, uv_0, uv_1)
                #print(T,B)
                #raw_tangents[i][tri[2]].append(T)
                #raw_bitangents[i][tri[2]].append(B)

                raw_tangents[i][p] = T
                raw_bitangents[i][p] = B

    #tangents = defaultdict(dict)
    #bitangents = defaultdict(dict)

    #for i, vtans in raw_tangents.items():
    #    for v, tans in vtans.items():
    #        tangents[i][v] = avg_vec3(tans)

    #for i, vbitans in raw_bitangents.items():
    #    for v, bitans in vbitans.items():
    #        bitangents[i][v] = avg_vec3(bitans)

    #return tangents, bitangents
    return raw_tangents, raw_bitangents

def get_native_tangent_bitangents(mesh, uv_islands):
    try: mesh.calc_tangents()
    except: return dict(), dict()

    tangents = defaultdict(dict)
    bitangents = defaultdict(dict)

    for i, uvi in enumerate(uv_islands):

        for p in uvi:
            pol = mesh.polygons[p]

            for loop in [mesh.loops[i] for i in pol.loop_indices]:

                if loop.vertex_index not in tangents[i]:
                    tangents[i][loop.vertex_index] = loop.tangent

                if loop.vertex_index not in bitangents[i]:
                    bitangents[i][loop.vertex_index] = loop.bitangent

    return tangents, bitangents

def debug_native_tangents(obj):
    try: obj.data.calc_tangents()
    except: return

    uv_layer = obj.data.uv_layers.active.data

    vts = []
    edgs = []

    i = 0
    for loop in obj.data.loops:
        v = obj.data.vertices[loop.vertex_index]

        vts.append(v.co.copy())
        vts.append(v.co + loop.tangent * 0.1)
        edgs.append((i, i+1))
        
        i += 2

        vts.append(v.co.copy())
        vts.append(v.co + loop.bitangent * 0.05)
        edgs.append((i, i+1))

        i += 2

        vts.append(v.co.copy())
        vts.append(v.co + loop.normal * 0.1)
        edgs.append((i, i+1))

        i += 2
        
    me = bpy.data.meshes.new("")
    me.from_pydata(vts, edgs, [])
    me.validate()
    me.update()
    
    ob = bpy.data.objects.new("Tangents", me)
    ob.matrix_world = obj.matrix_world.copy()
    scene = bpy.context.scene
    scene.objects.link(ob)
    scene.update()

def debug_mesh_tangents(obj, tangents):
    vts = []
    edgs = []
    
    i = 0
    for uvi, ts in tangents.items():
        for vid, t in ts.items():
            v = obj.data.vertices[vid]
            pos = v.co #* obj.matrix_world
            vts.append(pos)
            vts.append(pos + t * 0.1) 
        
            edgs.append((i, i+1))
            
            i += 2
        
    me = bpy.data.meshes.new("")
    me.from_pydata(vts, edgs, [])
    me.validate()
    me.update()
    
    ob = bpy.data.objects.new("Tangents", me)
    ob.matrix_world = obj.matrix_world.copy()
    scene = bpy.context.scene
    scene.objects.link(ob)
    scene.update()

def debug_mesh_tangents_1(obj, tangents):
    vts = []
    edgs = []
    
    i = 0
    for uvi, ts in tangents.items():
        for pid, t in ts.items():
            p = obj.data.polygons[pid]
            pos = p.center #* obj.matrix_world
            vts.append(pos)
            vts.append(pos + t * 0.1) 
        
            edgs.append((i, i+1))
            
            i += 2
        
    me = bpy.data.meshes.new("")
    me.from_pydata(vts, edgs, [])
    me.validate()
    me.update()
    
    ob = bpy.data.objects.new("Tangents", me)
    ob.matrix_world = obj.matrix_world.copy()
    scene = bpy.context.scene
    scene.objects.link(ob)
    scene.update()

def extract_uv_scale(loop, v1, v2, uv1, uv2):
    tangent = loop.tangent
    bitangent = loop.bitangent
    normal = loop.normal

    tbn = Matrix((tangent, bitangent, normal))
    tbn.invert()

    v_1 = v1.copy() * tbn
    v_2 = v2.copy() * tbn

    v_1 = Vector((v_1.x, v_1.y))
    v_2 = Vector((v_2.x, v_2.y))

    m1 = Matrix((uv1, uv2))
    m1.invert()

    m2 = Matrix((v_1, v_2))
    m = m1 * m2

    scale_x = m[0][0]
    scale_y = m[1][1]

    return scale_x, scale_y, v_1, v_2

def debug_tbn(obj, uv_islands):

    #obj.data.calc_tangents()
    uv_layer = obj.data.uv_layers.active.data

    mesh = bpy.data.meshes.new("TBN Debug")

    i = 0
    for uvi, pols in enumerate(uv_islands):
        #if uvi != 15: continue
        for p in pols:

            pol = obj.data.polygons[p]

            v0 = obj.data.vertices[pol.vertices[0]].co
            v1 = obj.data.vertices[pol.vertices[1]].co
            v2 = obj.data.vertices[pol.vertices[2]].co

            v1 = v1 - v0
            v2 = v2 - v0

            loop0 = obj.data.loops[pol.loop_indices[0]]
            loop1 = obj.data.loops[pol.loop_indices[1]]
            loop2 = obj.data.loops[pol.loop_indices[2]]

            uv0 = uv_layer[pol.loop_indices[0]].uv
            uv1 = uv_layer[pol.loop_indices[1]].uv
            uv2 = uv_layer[pol.loop_indices[2]].uv

            uv1 = uv1 - uv0
            uv2 = uv2 - uv0

            scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop0, v1, v2, uv1, uv2)

            if scale_x < 0 or scale_y < 0:
                scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop1, v1, v2, uv1, uv2)

            if scale_x < 0 or scale_y < 0:
                scale_x, scale_y, v_1, v_2 = extract_uv_scale(loop2, v1, v2, uv1, uv2)

            v1 = v_1
            v2 = v_2

            if scale_x < 200 and scale_y < 200: continue
            print(p)

            #print(p, scale_x, scale_y)

            # Debug

            #v1 = Vector((v1.x * 1/scale_x, v1.y * 1/scale_y))
            #v2 = Vector((v2.x * 1/scale_x, v2.y * 1/scale_y))

            v1 = uv0 + v1
            v2 = uv0 + v2

            mesh.vertices.add(3)

            mesh.vertices[i].co = Vector((uv0.x, uv0.y, 0.0))
            #mesh.vertices[i].co = Vector((0.0, 0.0, 0.0))
            mesh.vertices[i+1].co = Vector((v1.x, v1.y, 0.0))
            mesh.vertices[i+2].co = Vector((v2.x, v2.y, 0.0))

            create_face(mesh, i, i+1, i+2)

            i += 3

            uv1 = uv0 + uv1
            uv2 = uv0 + uv2

            mesh.vertices.add(3)

            mesh.vertices[i].co = Vector((uv0.x, uv0.y, 0.0))
            #mesh.vertices[i].co = Vector((0.0, 0.0, 0.0))
            mesh.vertices[i+1].co = Vector((uv1.x, uv1.y, 0.0))
            mesh.vertices[i+2].co = Vector((uv2.x, uv2.y, 0.0))

            create_face(mesh, i, i+1, i+2)

            i += 3

    mesh.validate()
    mesh.update()
    
    o = bpy.data.objects.new("TBN Debug", mesh)
    #o.matrix_world = obj.matrix_world
    o.draw_type = 'WIRE'
    #o.show_x_ray = True

    scene = bpy.context.scene
    scene.objects.link(o)
    #bpy.ops.object.select_all(action='DESELECT')
    #o.select = True
    #scene.objects.active = o
    #scene.update()


def debug_uv(obj): #, tangents, bitangents):

    uv_layer = obj.data.uv_layers.active.data

    mesh = bpy.data.meshes.new("UV Debug")

    i = 0
    for p in obj.data.polygons:

        uv0 = uv_layer[p.loop_indices[0]].uv
        uv1 = uv_layer[p.loop_indices[1]].uv
        uv2 = uv_layer[p.loop_indices[2]].uv

        mesh.vertices.add(3)

        mesh.vertices[i].co = Vector((uv0.x, uv0.y, 0.0))
        mesh.vertices[i+1].co = Vector((uv1.x, uv1.y, 0.0))
        mesh.vertices[i+2].co = Vector((uv2.x, uv2.y, 0.0))

        create_face(mesh, i, i+1, i+2)

        i += 3

    mesh.validate()
    mesh.update()
    
    o = bpy.data.objects.new("UV Debug", mesh)
    #o.matrix_world = obj.matrix_world
    o.draw_type = 'WIRE'
    #o.show_x_ray = True

    scene = bpy.context.scene
    scene.objects.link(o)
    #bpy.ops.object.select_all(action='DESELECT')
    #o.select = True
    #scene.objects.active = o
    #scene.update()

def get_list_of_vertex_connections(mesh):

    vc = defaultdict(list)

    for edge in mesh.edges:
        vc[edge.vertices[0]].append(edge.vertices[1])
        vc[edge.vertices[1]].append(edge.vertices[0])

    return vc

def get_curvatures(mesh, uv_islands, vcons):

    curvatures = {}

    #max_val = 1
    #min_val = -1
    #min_val = 0.5
    #max_val = 0.5

    combined = []

    for i, uvi in enumerate(uv_islands):
        curvatures[i] = {}
        for p in uvi:
            pol = mesh.polygons[p]

            for vid in pol.vertices:
                if vid in curvatures[i]: continue

                vk = mesh.vertices[vid]
                loop = [mesh.loops[l] for l in pol.loop_indices if mesh.loops[l].vertex_index == vid][0]

                num_neighbors = len(vcons[vid])

                A = np.zeros(num_neighbors*2, dtype=np.float32).reshape(num_neighbors, 2)
                B = np.zeros(num_neighbors, dtype=np.float32)

                for j, cvid in enumerate(vcons[vid]):
                    v = mesh.vertices[cvid]

                    t = v.co - vk.co

                    offset_x = loop.tangent.dot(t)
                    offset_y = loop.bitangent.dot(t)
                    offset_z = loop.normal.dot(t)

                    # Square x and y offset
                    offset_x = offset_x ** 2
                    offset_y = offset_y ** 2
                    #offset_x = pow(offset_x, 2)
                    #offset_y = pow(offset_y, 2)

                    A[j][0] = offset_x
                    A[j][1] = offset_y
                    B[j] = -offset_z

                    #print(A[j], B[j])

	        # Matrix least squares solution
                a1 = np.matmul(A.T, A)
                inv = np.linalg.inv(a1)
                a2 = np.matmul(inv, A.T)
                final = np.matmul(a2, B)

                #print(vid)
                #print(final)
                #for j in range(num_neighbors):
                #    z = final[0] * A[j][0] + final[1] * A[j][1]
                #    print(A[j], B[j], z, abs(B[j]-z))
                #print(vid, final)

                #if final[0] < min_val:
                #    min_val = final[0]

                #if final[1] < min_val:
                #    min_val = final[1]

                #if final[0] > max_val:
                #    max_val = final[0]

                #if final[1] > max_val:
                #    max_val = final[1]

                #print(vid, final)

                curvatures[i][vid] = final
                combined.append(final[0])
                combined.append(final[1])

    #combined = np.array(combined)
    #mean = np.mean(combined, axis=0)
    #sd = np.std(combined, axis=0)

    #span = abs(max_val - min_val)

    #if span < 0.0001:
    #    return 0.0, 1.0, curvatures

    #scaled_curvatures = {}

    #for i, vs in curvatures.items():
    #    scaled_curvatures[i] = {}
    #    for v, curv in vs.items():
    #        scaled_curvatures[i][v] = (curv - min_val) / span
    #        #print(scaled_curvatures[i][v])

    #print(min_val, max_val)
    min_val, span, scaled_curvatures = zip_island_vectors(combined, curvatures)

    #for i, vs in curvatures.items():
    #    for v, curv in vs.items():
    #        descaled = scaled_curvatures[i][v] * span + Vector((min_val, min_val))
    #        print(v, curv, descaled)

    #print(min_val, span)

    #return min_val, max_val, curvatures
    return min_val, span, scaled_curvatures

class YDebugMesh(bpy.types.Operator):
    """Debug Mesh"""
    bl_idname = "node.y_debug_mesh"
    bl_label = "Debug Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH' and len(context.object.data.uv_layers) > 0

    def execute(self, context):

        scene = context.scene
        obj = context.object

        flat = False

        # Get list of uv islands
        uv_islands = get_list_of_uv_islands(obj)
        #for i, uvi in enumerate(uv_islands):
        #    print(i)
        #    for f in uvi:
        #        print(f)

        # Make all face flat for correct scale calculation
        ori_smooth = []
        for f in obj.data.polygons:
            ori_smooth.append(f.use_smooth)
            f.use_smooth = False

        try: obj.data.calc_tangents()
        except:
            self.report({'ERROR'}, "Cannot do it to a mesh with ngons!")
            return {'CANCELLED'}

        # Get list of tris for each polygons
        #poltris = get_polygon_tris_dict(obj.data)
        #debug_mesh_tris(scene, obj, poltris)

        # Get uv islands vertex index
        #uvi_verts = defaultdict(list)

        #for i, uvi in enumerate(uv_islands):
        #    for p in uvi:
        #        for v in obj.data.polygons[p].vertices:
        #            if v not in uvi_verts[i]:
        #                uvi_verts[i].append(v)

        #print(uvi_verts)


        #tangents, bitangents = get_native_tangent_bitangents(obj.data, uv_islands)
        #debug_mesh_tangents(obj, tangents)

        #for i, uvi_tans in tangents.items():
        #    print(i)
        #    for v, t in uvi_tans.items():
        #        print(v, t)

        #if not tangents:
            #mtangents, mbitangents = get_manual_tangent_bitangents(obj.data, uv_islands, poltris)
        #tangents, bitangents = get_manual_tangent_bitangents(obj.data, uv_islands, poltris)
            #debug_mesh_tangents(obj, mtangents)
        #debug_mesh_tangents_1(obj, tangents)
        #debug_uv(obj) #, tangents, bitangents)
        #debug_native_tangents(obj)

        scale_min, scale_span, scales = get_uv_scale_factor(obj.data, uv_islands)

        #return {'FINISHED'}

        obj.data.yp.parallax_scale_min = scale_min
        obj.data.yp.parallax_scale_span = scale_span

        # Revert original polygon smooth
        for i, f in enumerate(obj.data.polygons):
            f.use_smooth = ori_smooth[i]

        # Recalculate tangents
        obj.data.calc_tangents()
        
        vcons = get_list_of_vertex_connections(obj.data)
        #for i, c in vcons.items():
        #    print(i, c)
        #print(vcons)
        
        curvature_min, curvature_span, curvatures = get_curvatures(obj.data, uv_islands, vcons)

        obj.data.yp.parallax_curvature_min = curvature_min
        obj.data.yp.parallax_curvature_span = curvature_span

        #debug_tbn(obj, uv_islands)

        #for i, pol_scales in scales.items():
        #    for p, scale in pol_scales.items():
        #        #print(p, scale)
        #        pass

        # Scale vertex colors
        sca_vcol = obj.data.vertex_colors.get('_scale')
        if not sca_vcol:
            sca_vcol = obj.data.vertex_colors.new('_scale')

        # Curvature vertex colors
        cur_vcol = obj.data.vertex_colors.get('_curvature')
        if not cur_vcol:
            cur_vcol = obj.data.vertex_colors.new('_curvature')

        for i, ps in enumerate(uv_islands):
            for p in ps:
                pol = obj.data.polygons[p]

                for l in pol.loop_indices:
                    scale = scales[i][p]
                    sca_vcol.data[l].color = Vector((scale[0], scale[1], 0.0))

                # Set curvature vertex color
                for v in pol.vertices:

                    curv = curvatures[i][v]

                    loop = [obj.data.loops[l] for l in pol.loop_indices if obj.data.loops[l].vertex_index == v][0]
                    cur_vcol.data[loop.index].color = Vector((curv[0], curv[1], 0.0))

        #bpy.ops.object.mode_set(mode='EDIT')

        # Set material value

        #mat = obj.active_material
        curvature_tree = bpy.data.node_groups.get('curvature')
        if curvature_tree:
            mul = curvature_tree.nodes.get('mul')
            if mul: mul.outputs[0].default_value = curvature_span
            add = curvature_tree.nodes.get('add')
            if add: add.outputs[0].default_value = curvature_min

        uv_scale_tree = bpy.data.node_groups.get('uv_scale')
        if uv_scale_tree:
            mul = uv_scale_tree.nodes.get('mul')
            if mul: mul.outputs[0].default_value = scale_span
            add = uv_scale_tree.nodes.get('add')
            if add: add.outputs[0].default_value = scale_min

        return {'FINISHED'}

class YTestRay(bpy.types.Operator):
    """Test Ray"""
    bl_idname = "node.y_test_ray"
    bl_label = "Test Ray"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def formula(self, value):
        return -1.0*value*value

    def execute(self, context):

        vts = []
        edgs = []

        offset = 1.0
        for i in range(21):
            #x = -0.1 * i
            x = offset - 0.1 * i
            y = self.formula(x)

            vts.append(Vector((x, y, 0.0)))
            #print(vts[len(vts)-1])
            if i > 0:
                edgs.append((i-1, i))
                #print(edgs[len(edgs)-1])

        #print(len(vts), len(edgs))

        me = bpy.data.meshes.new("")
        me.from_pydata(vts, edgs, [])
        me.validate()
        me.update()
        
        ob = bpy.data.objects.new("Curvature", me)
        #ob.matrix_world = obj.matrix_world.copy()
        scene = bpy.context.scene
        scene.objects.link(ob)
        scene.update()

        vts = []
        edgs = []

        prev_yc = 0.0
        prev_x = 0.0

        steps = 10
        height = 1.0

        for i in range(steps+1):
            x = 1/steps * i
            y = -height/steps * i

            yc = self.formula(x)

            #x = (x - (yc - prev_yc)) * sqrt(abs(x))
            #x = (prev_x + yc - prev_yc) * sqrt(abs(x))

            if i > 0:

                #x_axis = Vector((-copysign(1.0, x), -yc/abs(x)))
                #y_axis = Vector((-x_axis.y, x_axis.x)).normalized()
                #x_axis = Vector((1.0, copysign(1.0, x) * yc/abs(x))) #.normalized()
                #y_axis = Vector((-x_axis.y, x_axis.x)).normalized()
                
                #x_ = Vector((x, 0))
                #x_transform  = Vector((x, yc)) - x_
                tangent = Vector((x, yc))
                tangent_norm = tangent.normalized()
                bitangent = Vector((-tangent_norm.y, tangent_norm.x)).normalized()

                tangent *= copysign(1.0, x)
                bitangent *= copysign(1.0, x)

                #if x < 0:
                #    tangent = Vector((-tangent.x, -tangent.y))
                #    bitangent = Vector((-bitangent.x, -bitangent.y))

                tangent = tangent/tangent.x

                print(tangent, bitangent)

                mat = Matrix((tangent, bitangent)) #.inverted()

                #mat = Matrix((x_axis, y_axis)) #.inverted()
                #mat = Matrix(((x_axis.x, y_axis.x), (x_axis.y, y_axis.y)))

                #print()

                #print(mat)

                mat = mat.inverted()

                #print(mat)
                #print(mat.determinant())

                new_vec = Vector((x, y)) * mat

                #mat = Matrix((
                #    Vector((-copysign(1.0, x), -yc/x)),
                #    Vector((y, y))
                #    ))

                vts.append(Vector((new_vec.x, new_vec.y, 0.0)))

                edgs.append((i-1, i))
            else:
                vts.append(Vector((x, y, 0.0)))

            #prev_yc = yc
            #prev_x = x

        me = bpy.data.meshes.new("")
        me.from_pydata(vts, edgs, [])
        me.validate()
        me.update()
        
        ob = bpy.data.objects.new("Test Ray", me)
        #ob.matrix_world = obj.matrix_world.copy()
        scene = bpy.context.scene
        scene.objects.link(ob)
        scene.update()

        return {'FINISHED'}

def register():
    #bpy.utils.register_class(YDebugMesh)
    #bpy.utils.register_class(YTestRay)
    pass

def unregister():
    #bpy.utils.unregister_class(YDebugMesh)
    #bpy.utils.unregister_class(YTestRay)
    pass
