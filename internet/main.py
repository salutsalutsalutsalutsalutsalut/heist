from fastapi import FastAPI, HTTPException, Query
import random

app = FastAPI()

def read_entries_from_file(file_path):
    with open(file_path, 'r') as file:
        entries = []
        for line in file:
            entry = {}
            parts = line.strip().split(', ')
            for part in parts:
                key_value = part.split(': ')
                if len(key_value) == 2:
                    key, value = key_value
                    entry[key.strip()] = value.strip()
                else:
                    
                    continue
            if entry:  
                entries.append(entry)
    return entries


entries = read_entries_from_file('a.txt')


def get_random_entry(entries, server=None, title=None):
    filtered_entries = entries[:]
    if server:
        filtered_entries = [entry for entry in filtered_entries if 'Server' in entry and server.lower() in entry['Server'].lower()]
    if title:
        filtered_entries = [entry for entry in filtered_entries if 'Title' in entry and title.lower() in entry['Title'].lower()]
    if not filtered_entries:
        raise HTTPException(status_code=404, detail="No entries found matching the criteria")
    
    selected_entry = random.choice(filtered_entries)
    return selected_entry

@app.get("/random/")
def random_entry(server: str = Query(None), title: str = Query(None)):
    return get_random_entry(entries, server, title)

@app.get("/servers/")
def get_servers():
    servers = set(entry['Server'] for entry in entries if 'Server' in entry)
    return {'servers': list(servers)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
