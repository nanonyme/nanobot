create table Users (uid integer primary key, name text);
create table Usermask (mask text primary key, uid integer, foreign key(uid) references Users(uid), unique(mask));
create table Roles (oid integer primary key, name text, unique(name));
create table UserRoles (uid integer, oid integer, primary key(uid, oid));

