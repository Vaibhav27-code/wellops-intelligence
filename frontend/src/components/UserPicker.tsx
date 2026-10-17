import React from 'react';
import { buildAppUser, DEFAULT_USERS, useStore } from '../store';
import { api } from '../api/client';
import type { AppUser } from '../types';
import { ChevronDown, User } from 'lucide-react';

export function UserPicker() {
  const { users, setUsers, currentUser, setUser } = useStore();
  const [open, setOpen] = React.useState(false);

  // Load all 15 users from backend /users endpoint on mount
  React.useEffect(() => {
    let mounted = true;
    api
      .getUsers()
      .then((res) => {
        if (mounted && res.users && res.users.length > 0) {
          const backendAppUsers = res.users.map((u, i) => buildAppUser(u, i));
          const userMap = new Map<string, AppUser>();
          DEFAULT_USERS.forEach((u) => userMap.set(u.user_id, u));
          backendAppUsers.forEach((u) => userMap.set(u.user_id, u));
          const appUsers = Array.from(userMap.values());
          setUsers(appUsers);
          // Keep current selection if valid, or default to Michael Turner (U-201)
          const found = appUsers.find((u) => u.user_id === currentUser.user_id);
          const defaultUser = appUsers.find((u) => u.user_id === 'U-201') ?? appUsers[0];
          setUser(found ?? defaultUser);
        }
      })
      .catch((err) => {
        console.warn('Could not load users from backend; using default fleet users:', err);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="user-picker">
      <button
        className="user-picker__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Switch user (switches private conversation history)"
      >
        <span
          className="user-picker__avatar"
          style={{ background: currentUser.avatar_color }}
        >
          <User size={14} color="#fff" />
        </span>
        <span className="user-picker__name">{currentUser.display_name}</span>
        <ChevronDown size={14} className={open ? 'rotated' : ''} />
      </button>

      {open && (
        <ul className="user-picker__dropdown" role="listbox">
          {users.map((u: AppUser) => (
            <li
              key={u.user_id}
              role="option"
              aria-selected={u.user_id === currentUser.user_id}
              className={`user-picker__option ${u.user_id === currentUser.user_id ? 'active' : ''}`}
              onClick={() => {
                setUser(u);
                setOpen(false);
              }}
            >
              <span
                className="user-picker__avatar"
                style={{ background: u.avatar_color }}
              >
                <User size={14} color="#fff" />
              </span>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: 600 }}>{u.name ?? u.display_name}</span>
                <span style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>
                  {u.role ? u.role.replace(/_/g, ' ') : 'operator'} {u.team_id ? `· ${u.team_id}` : ''}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
