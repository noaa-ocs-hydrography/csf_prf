def demo():
    """
    Accessing polygon geometries with arcpy will seperate inner features with a 'None' object.
    This script is a test of how to obtain all the individual geometries. 
    """
    
    inner_features = []
    outer_features = []
    row = [[1, 2, 3, 4, None, 5, 6, 7], 
            [1, 2, 3, 4, None, 5, 6, 7, None, 8, 9, 10, None, 11, 12, 13, None, 14, 15, 16, None, 17, 18, 19, None, 20]]
    for part in row:
        print('part:', part)
        none_indexes = [i for i, point in enumerate(part) if point is None]
        print('Num of inner:', len(none_indexes))
        if len(none_indexes) == 1: # only 1 inner polygon
            outer_features.append(part[0:none_indexes[0]]) # First polygon is outer
            inner_features.append(part[none_indexes[0]+1:len(part)]) # capture last inner
            print('outer:', part[0:none_indexes[0]])
            print('inner:', part[none_indexes[0]+1:len(part)])
        else:
            for i, (current, next) in enumerate(zip(none_indexes[:-1], none_indexes[1:])):
                if i == 0: # first one
                    print(i, 'outer:', part[0:current])
                    print(i, 'inner:', part[current+1:next])
                    outer_features.append(part[0:current]) # First polygon is outer
                    inner_features.append(part[current+1:next]) # capture first inner
                elif i == len(none_indexes) - 2: # last one
                    print(i, 'inner:', part[current+1:next], part[next+1:len(part)])
                    inner_features.append(part[current+1:next]) # capture current inner
                    inner_features.append(part[next+1:len(part)]) # capture last inner
                else: # in between
                    print(i, 'inner:', part[current+1:next])
                    inner_features.append(part[current+1:next]) # capture current inner

    print('Inner:', len(inner_features))
    print('Outer:', len(outer_features))

if __name__ == '__main__':
    demo()