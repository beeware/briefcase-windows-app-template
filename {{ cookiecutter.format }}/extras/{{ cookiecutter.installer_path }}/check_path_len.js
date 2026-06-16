// Validate that the selected INSTALLFOLDER is short enough to accommodate
// every file this MSI is about to install, given the Windows MAX_PATH
// limit of 260 characters (32767 if long paths are enabled)
//
// Outputs (set on the running MSI session):
//
//   INSTALLDIR_TOO_LONG       "1" if the selected path is too long, else ""
//   INSTALLDIR_TOO_LONG_MSG   A human-readable diagnostic message,
//                             populated whether or not the check failed

// Windows MAX_PATH minus the null terminator.
var MAX_PATH_LEN = 259;
var LONG_PATH_LEN = 32766;

try {
    var shell = new ActiveXObject("WScript.Shell");
    var enabled = shell.RegRead(
        "HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\LongPathsEnabled");
    if (enabled === 1 || enabled === "1") {
        MAX_PATH_LEN = LONG_PATH_LEN;
    }
} catch (e) {
    // Key missing or unreadable — fall through to the conservative limit.
}

var MSG_INFO = 0x04000000;  // INSTALLMESSAGE_INFO

var installFolder = Session.Property("INSTALLFOLDER");

// INSTALLFOLDER is always set with a trailing backslash by MSI. Strip it
// for length accounting; we add exactly one separator below when joining
// to the relative path.
if (installFolder.charAt(installFolder.length - 1) === "\\") {
    installFolder = installFolder.substring(0, installFolder.length - 1);
}

// --------------------------------------------------------------------------
// Build a map of Directory id -> resolved relative path from INSTALLFOLDER.
//
// The Directory table is a tree. Each row has:
//   Directory          - the row's id
//   Directory_Parent   - parent row's id (NULL for the root)
//   DefaultDir         - the directory name, possibly in the form
//                        "shortname|longname" or
//                        "targetshort:sourceshort|targetlong:sourcelong"
//
// We resolve each id by walking up to INSTALLFOLDER, collecting long names.
// Directories above INSTALLFOLDER (e.g. ProgramFiles64Folder, TARGETDIR)
// don't contribute to the relative path, since they are subsumed by the
// user's selection.
// --------------------------------------------------------------------------

var dirParent = {};
var dirName = {};

var view = Session.Database.OpenView(
    "SELECT `Directory`, `Directory_Parent`, `DefaultDir` FROM `Directory`");
view.Execute();
while (true) {
    var rec = view.Fetch();
    if (rec === null) {
        break;
    }
    var id = rec.StringData(1);
    dirParent[id] = rec.StringData(2);

    var raw = rec.StringData(3);
    // Pick the long name half of "short|long" if present.
    var pipe = raw.indexOf("|");
    var longPart = pipe >= 0 ? raw.substring(pipe + 1) : raw;
    // Pick the target half of "target:source" if present.
    var colon = longPart.indexOf(":");
    if (colon >= 0) {
        longPart = longPart.substring(0, colon);
    }
    dirName[id] = longPart;
}

// Resolve a directory id to its path relative to INSTALLFOLDER.
// Returns "" for INSTALLFOLDER itself, and null for ids outside its subtree.
function relPath(dirId) {
    var parts = "";
    var current = dirId;
    while (true) {
        if (current === "INSTALLFOLDER") {
            return parts;
        }
        if (!dirParent.hasOwnProperty(current)) {
            // Walked off the top without finding INSTALLFOLDER.
            return null;
        }
        var name = dirName[current];
        if (name !== "." && name !== "") {
            parts = parts === "" ? name : name + "\\" + parts;
        }
        current = dirParent[current];
    }
}

// --------------------------------------------------------------------------
// Walk the File table, computing each file's full path relative to
// INSTALLFOLDER and tracking the maximum length.
// --------------------------------------------------------------------------

var longestLen = 0;
var longestPath = "";

view = Session.Database.OpenView(
    "SELECT `File`.`FileName`, `Component`.`Directory_` "
    + "FROM `File`, `Component` "
    + "WHERE `File`.`Component_` = `Component`.`Component`");
view.Execute();
while (true) {
    var fileRec = view.Fetch();
    if (fileRec === null) {
        break;
    }

    var fileRaw = fileRec.StringData(1);
    var filePipe = fileRaw.indexOf("|");
    var fileLong = filePipe >= 0 ? fileRaw.substring(filePipe + 1) : fileRaw;

    var dirRel = relPath(fileRec.StringData(2));
    if (dirRel !== null) {
        var candidate = dirRel === "" ? fileLong : dirRel + "\\" + fileLong;
        if (candidate.length > longestLen) {
            longestLen = candidate.length;
            longestPath = candidate;
        }
    }
}

// --------------------------------------------------------------------------
// Compare against the limit and publish the result.
// --------------------------------------------------------------------------

var totalLen = installFolder.length + 1 + longestLen;  // +1 for joining "\"
var budget = MAX_PATH_LEN - longestLen - 1;
var msg;

if (totalLen > MAX_PATH_LEN) {
  msg = "The selected install location is too long.\r\n\r\n"
        + "Hello World must be intalled into a location with a maximum\r\n"
        + "path length of " + budget + " characters. The selected path has a length\r\n"
        + "of " + installFolder.length + " characters. Please select a shorter install location.\r\n";
    Session.Property("INSTALLDIR_TOO_LONG") = "1";
} else {
    msg = "Install path length OK: " + totalLen + " of " + MAX_PATH_LEN
        + " characters used (longest internal path: " + longestLen + ").";
    Session.Property("INSTALLDIR_TOO_LONG") = "";
}

Session.Property("INSTALLDIR_TOO_LONG_MSG") = msg;

// Always write to the MSI log, regardless of UI level.
var logRec = Installer.CreateRecord(1);
logRec.StringData(0) = "Briefcase install path check: [1]";
logRec.StringData(1) = msg;
Session.Message(MSG_INFO, logRec);
