-- Move staged file from `arg_source` location to `arg_destination`.
--
-- Runs on a FlashAir WiFi SD card.
-- Example usage: http://flashair/MUSIC/_fam_move_touch.lua?staged.bin%2015295%20/MUSIC/subdir/artist%20-%20title.mp3
-- May be in zero, one, or more subdirectories. Also touch (change mtime) file after moving, used to check if file has
-- changed on FlashAirMusic server.
-- https://github.com/Robpol86/FlashAirMusic

MAX_MTIME = 4294967295  -- 0xFFFFFFFF
MIN_MTIME = 1000000000

arg_source = (arg[1] or ''):gsub('^%s*(.-)%s*$', '%1')  -- FlashAir seems to add a newline on the last arg item.
arg_mtime = (arg[2] or ''):gsub('^%s*(.-)%s*$', '%1')
arg_destination = table.concat({select(3, unpack(arg))}, ' '):gsub('^%s*(.-)%s*$', '%1')
return_data = {error='', arg_source=arg_source, arg_mtime=arg_mtime, arg_destination=arg_destination}


-- Terminate program early.
function exit(status, message)
    if message then return_data['error'] = message end
    print(('HTTP/1.1 %s'):format(status))
    print('Content-Type: application/json')
    print('')
    print(cjson.encode(return_data))
    os.exit()  -- Calling os.anything causes script to exit/crash.
end

-- String endswith. From: http://lua-users.org/wiki/StringRecipes
function string.endswith(str, tail)
   return tail == '' or string.sub(str, -string.len(tail)) == tail
end

-- Parent directory path.
function dirname(path)
    if path:sub(-1) == '/' then path = path:gsub('^(.-)/*$', '%1') end  -- rstrip / characters.
    local parent, count = path:gsub('^(.*)/.-$', '%1')
    if count == 0 then return '' end  -- dirname('file') == ''
    if parent == '' then return '/' end  -- dirname('/dir') == '/'
    return parent
end

-- Recursive mkdir.
function mkdir_p(path)
    local path = path:gsub('^/*(/.-)$', '%1'):gsub('^(.-)/*$', '%1'):gsub('//+', '/')
    if path == '' or lfs.attributes(path) then return false end
    local dir
    local pos = 1
    if path:sub(1, 1) == '/' then pos = 2 end
    while true do
        pos = path:find('/', pos)
        if not pos then break end
        dir = path:sub(0, pos - 1)
        if not lfs.attributes(dir) then lfs.mkdir(dir) end
        pos = pos + 1
    end
    lfs.mkdir(path)
    return true
end

-- Get current time in FTIME format.
function get_current_time()
    io.open('_fam_empty_file.bin', 'w'):close()
    local ftime = lfs.attributes('_fam_empty_file.bin', 'modification')
    fa.remove('_fam_empty_file.bin')
    return ftime
end

-- Set current time. From https://sites.google.com/site/gpsnmeajp/electricmemo/flashairnortcwo-shiu
function set_current_time(ftime)
    local ftime = tonumber(ftime)
    local year = bit32.band(bit32.rshift(ftime, 25), 0x7F)
	local month = bit32.band(bit32.rshift(ftime, 21), 0xF)
	local day = bit32.band(bit32.rshift(ftime,16), 0x1F)
    local hour = bit32.band(bit32.rshift(ftime, 11), 0x1F)
    local minute = bit32.band(bit32.rshift(ftime, 5), 0x3F)
    local second = bit32.band(ftime, 0x3F)
    local ymd = bit32.bor(bit32.lshift(year, 9), bit32.lshift(month, 5), day)
    local hms = bit32.bor(bit32.lshift(hour, 11), bit32.lshift(minute, 5), second)
    fa.SetCurrentTime(ymd, hms)  -- Undocumented method.
end

-- Touch file, stupid FlashAir has lfs but only three of its methods.
function touch(path, ftime)
    -- Read last byte of file, and then re-write it to cause filesystem to change mtime.
    local handle = io.open(path, 'r+')
    local size = handle:seek('end')
    handle:seek('set', size - 1)
    local byte = handle:read('*a')
    handle:seek('set', size - 1)
    handle:write(byte)
    -- Now change the system time before closing file which is when mtime is written to filesystem.
    local now = get_current_time()
    set_current_time(ftime)
    handle:close()
    set_current_time(now)
end


-- Error handling.
if arg_source == '' then exit('400 Bad Request', 'arg_source (arg[1]) empty.') end
if lfs.attributes(arg_source, 'mode') ~= 'file' then exit('400 Bad Request', 'arg_source not found or not a file.') end
if arg_mtime == '' then exit('400 Bad Request', 'arg_mtime (arg[2]) empty.') end
if not tonumber(arg_mtime) then exit('400 Bad Request', 'arg_mtime not a number.') end
if tonumber(arg_mtime) < MIN_MTIME then exit('400 Bad Request', ('arg_mtime under %d.'):format(MIN_MTIME)) end
if tonumber(arg_mtime) > MAX_MTIME then exit('400 Bad Request', ('arg_mtime over %d.'):format(MAX_MTIME)) end
if arg_destination == '' then exit('400 Bad Request', 'arg_destination (arg[3:]) empty.') end
if not arg_destination:endswith('.mp3') then exit('400 Bad Request', "arg_destination doesn't end with .mp3.") end


-- Prepare destination.
if lfs.attributes(arg_destination) then
    fa.remove(arg_destination)
elseif not lfs.attributes(dirname(arg_destination)) then
    mkdir_p(dirname(arg_destination))
end


-- Touch and move.
touch(arg_source, arg_mtime)
fa.rename(arg_source, arg_destination)


-- Success.
exit('200 OK')
