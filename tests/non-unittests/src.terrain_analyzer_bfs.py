import sys
from terrain_analyzer import PathAnalyzer
import terrain_analyzer

sys.path.append("../../src")
pathextractor = PathAnalyzer()

pathextractor.load("../unittest_data/mirror_touched_sea2.platform")
print('platforms', pathextractor.platforms)
pathextractor.generate_solution_dict()

for key, val in pathextractor.platforms.items():
    print(val)
    print(val.solutions)
    print(val.last_visit)
    print("-------------------")

# start_hash = input("current location?")
# goal_hash = input("goal hash?")

solution = pathextractor.pathfind('6029314b', '0f9c84c4')
assert solution and len(solution) == 2 and solution[0].method == terrain_analyzer.METHOD_TELEPORTUP and solution[1].method == terrain_analyzer.METHOD_TELEPORTUP

solution = pathextractor.pathfind('a12ed5e3', '0f9c84c4')
print(solution)

# for solution in pathextractor.pathfind(start_hash, goal_hash):
#     print(solution.method, solution.to_hash)
