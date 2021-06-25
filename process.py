import os

def process_wtharvey():
    files = ["wtharvey_mate2.txt", "wtharvey_mate3.txt", "wtharvey_mate4.txt"]
    target = "wtharvey.txt"
    folder = 'E:\Workshop\project\RenChess\data'
    id = 1
    fw = open(os.path.join(folder, target), 'w')
    puzzles = ""

    for m, file in enumerate(files):
        f = open(os.path.join(folder, file), 'r')
        context = f.readlines()
        i = 0
        
        while i < len(context):
            line = context[i]
            if len(line.strip()) == 0:
                i += 1
            else:
                fen = context[i+1].strip()
                start = fen.split(" ")[1]
                if start == "w":
                    s = "White"
                elif start == "b":
                    s = "Black"
                else:
                    print("Error reading start side: %s, fen = %s" % (start, fen))
                    i += 3
                    continue
                puzzles += "%d %s Mates in %d\n%s\n%s\n\n" % (id, s, m+2, fen, context[i+2].strip())
                id += 1
                i += 3
        print(file + " completed.")
    fw.write(puzzles)
    fw.close()
    print("Done")

def process_5334():
    problems = "polgar_5334.pgn"
    solution = "polgar_5334_solution.txt"
    folder = 'E:\Workshop\project\RenChess\data'
    target = "polgar_5334.txt"
    game = ""
    fp = open(os.path.join(folder, problems), 'r')
    fs = open(os.path.join(folder, solution), 'r')
    fw = open(os.path.join(folder, target), 'w')
    puzzles = ""

    problem_context = fp.readlines()
    solution_context = fs.readlines()
    ip, isol, index = 0, 0, 0
    while ip < len(problem_context):
        line = problem_context[ip]
        if line.startswith("[White "):
            # [White "4212 Black Mate in Three"]
            # [White "White Endgame to Draw 5069"]
            game = " ".join(line[1:-1].split(" ")[1:])[1:-1]
            if game[-1] == "\"":
                game = game[:-1]
        elif line.startswith("[FEN "):
            fen = " ".join(line[1:-1].split(" ")[1:])[1:-2]
            items = game.split(" ")
            if game[0].isdigit():
                id = int(items[0])
                game = " ".join([str(id)] + items[1:])
            else:
                id = int(items[-1])
                game = " ".join([items[-1]] + items[:-1])
            sol = solution_context[index].split(" ")
            index += 1
            if id > 1 and int(sol[0]) != id:
                print("Problem index don't match: %s\nSolution=%s" % (game, " ".join(sol)))
                ip += 1
                continue
            puzzles += "%s\n%s\n%s\n\n" % (game, fen, " ".join(sol[1:]))
        ip += 1
    fw.write(puzzles)
    fw.close()
    print("Done")

def clean_5334():
    puzzle = "polgar_5334.txt"
    target = "polgar_5334_2.txt"
    folder = 'E:\Workshop\project\RenChess\data'
    fp = open(os.path.join(folder, puzzle), 'r')
    fw = open(os.path.join(folder, target), 'w')
    puzzle_context = fp.readlines()
    results = ""
    i = 0
    for line in puzzle_context:
        for c in line:
            o = ord(c)
            if o > 31 and o < 127:
                results += c
        results += "\n"
    fw.write(results)
    fw.close()
    print("Done")

def check_5334():
    puzzle = "polgar_5334.txt"
    folder = 'E:\Workshop\project\RenChess\data'
    fp = open(os.path.join(folder, puzzle), 'r')
    puzzle_context = fp.readlines()
    i = 0
    id = 0
    while i < len(puzzle_context) - 3:
        try:
            id = int(puzzle_context[i].split(" ")[0])
        except:
            print("Error in puzzle %d: %s" % (id, puzzle_context[i]))
            break
        if len(puzzle_context[i+1].strip()) == 0:
            print("Error in puzzle %d: %s" % (id, puzzle_context[i+1]))
            break
        if puzzle_context[i+2][0] != '1':
            print("Error in puzzle %d: %s" % (id, puzzle_context[i+2]))
            break
        if len(puzzle_context[i+3].strip()) > 0:
            print("Error in space line under puzzle %d" % id)
            break
        i += 4
    print("Done")

check_5334()