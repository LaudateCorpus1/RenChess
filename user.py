import os
import time
import configparser
import heapq

class User:
    def __init__(self):
        self.config = configparser.ConfigParser()
        user_file = os.path.join(os.getcwd(), "data\\user.ini")
        self.config.read(user_file)
        self.record = configparser.ConfigParser()
        record_file = os.path.join(os.getcwd(), "data\\record.txt")
        self.record.read(record_file)

    def add_activity(self, puzzle_set, puzzle_id, result):
        id_str = str(puzzle_id)
        days = int((time.time() - 1609488000) / 86400)   # number of days since 2021/01/01
        if puzzle_set not in self.record:
            self.record[puzzle_set] = {id_str: str(days) + " 0"}
        elif id_str not in self.record[puzzle_set]:
            self.record[puzzle_set][id_str] = str(days) + " 0"
        else:
            old_stage = int(self.record[puzzle_set][id_str].split(" ")[1])
            # Go to next stage if S rank is cleared. Otherwise go back to previous stage
            new_stage = old_stage + 1 if result == "S" else max(old_stage - 1, 0)
            if new_stage < 7:
                self.record[puzzle_set][id_str] = str(days) + " " + str(new_stage)
            else:
                self.record[puzzle_set].pop(id_str)

    def save_files(self):
        user_file = os.path.join(os.getcwd(), "data\\user.ini")
        with open(user_file, 'w') as configfile:
            self.config.write(configfile)
        record_file = os.path.join(os.getcwd(), "data\\record.txt")
        with open(record_file, 'w') as recordfile:
            self.record.write(recordfile)

    def get_review_items(self):
        memory_curve = {0: 1, 1: 2, 2: 3, 3: 5, 4: 8, 5: 13, 6: 21}
        today = int((time.time() - 1609488000) / 86400)   # number of days since 2021/01/01
        review_items = []
        max_item = int(self.config["User"]["max_review_items"])
        for section in self.record:
            for item in self.record[section]:
                records = self.record[section][item].split(" ")
                days, stage = int(records[0]), int(records[1])
                # review lower stage first. In the same stage, review older puzzle first
                idx = -1000 * memory_curve[stage] + (today - days)
                if len(review_items) < max_item:
                    heapq.heappush(review_items, (idx, section, item))
                elif idx > review_items[0][0]:
                    heapq.heapreplace(review_items, (idx, section, item))
        results = [heapq.heappop(review_items)[1:] for _ in range(len(review_items))]
        return results[::-1]    # reverse order
        
