import datetime
import logging
import json
import pytz

import json_log_formatter

# TODO(jlewi): Might be better to just write it
# as a json list
def write_items_to_json(output_file, results):
  with open(output_file, "w") as hf:
    for i in results:
      json.dump(i, hf)
      hf.write("\n")
  logging.info("Wrote %s items to %s", len(results), output_file)


pacific = pytz.timezone("US/Pacific")

def now():
  """Return the current time with timezone information."""
  # see https://julien.danjou.info/python-and-timezones/
  # Need to attach a time zone
  return datetime.datetime.now(tz=pacific)

class CustomisedJSONFormatter(json_log_formatter.JSONFormatter):
  """A custom formatter to produce logs in json format."""
  def json_record(self, message, extra, record):
    extra['message'] = message

    extra["filename"] = record.pathname
    extra["line"] = record.lineno
    extra["level"] = record.levelname
    if "time" not in extra:
      extra["time"] = now().isoformat()
    extra["thread"] = record.thread
    extra["thread_name"] = record.threadName
    return extra
