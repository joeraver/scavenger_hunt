INSERT INTO puzzle (id, point_value, trigger_word, response, location, script, parent_puzzle_id) VALUES (1, 5, 'table', 'you found a table! respond with "floop" now.', 'First Floor', null, null);
INSERT INTO puzzle (id, point_value, trigger_word, response, location, script, parent_puzzle_id) VALUES (2, 10, 'chair', 'and now you found a chair. respond with "bar"', 'First Floor', null, null);
INSERT INTO puzzle (id, point_value, trigger_word, response, location, script, parent_puzzle_id) VALUES (3, 2, 'first', 'what comes next?', 'First Floor', null, null);
INSERT INTO puzzle (id, point_value, trigger_word, response, location, script, parent_puzzle_id) VALUES (4, 4, 'second', 'and after that?', 'First Floor', null, 3);
INSERT INTO puzzle (id, point_value, trigger_word, response, location, script, parent_puzzle_id) VALUES (5, 6, 'third', 'this is the last one', 'First Floor', null, 4);
