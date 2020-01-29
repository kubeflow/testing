"""Some helper functions for test assertions"""

def assert_lists_equal(left, right):
  message = "Lists are not equal; {0}!={1}".format(left, right)
  assert len(left) == len(right), message

  for i, _ in enumerate(left):
    item_message = (message +
                    "\n; item {0} doesn't match {1}!={2}".format(i, left[i],
                                                                 right[i]))
    assert left[i] == right[i], item_message


def assert_dicts_equal(left, right, item_checker=None):
  """Check if dictionaries are equal.

  Args:
    item_checker: (Optional): Assert if dictionary items are equal
  """
  left_keys = set(left.keys())
  right_keys = set(right.keys())

  message = [f"{left} != {right}"]

  is_equal = True

  if left_keys - right_keys:
    is_equal = False
    message.append(f"Left has extra keys {left_keys - right_keys}")

  if right_keys - left_keys:
    is_equal = False
    message.append(f"right has extra keys {right_keys - left_keys}")

  common_keys = left_keys.intersection(right_keys)

  assert is_equal, "\n".join(message)

  for k in common_keys:
    if item_checker:
      assert item_checker(left[k], right[k])
    else:
      assert left[k] == right[k], f"{left[k]}!={right[k]}"


