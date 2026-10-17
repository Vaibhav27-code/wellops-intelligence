import React from 'react';
import { USERS, useStore } from '../store';
import type { AppUser } from '../types';
import { ChevronDown, User } from 'lucide-react';

export function UserPicker() {
  const { currentUser, setUser } = useStore();
  const [open, setOpen] = React.useState(false);

  return (
    <div className="user-picker">
      <button
        className="user-picker__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
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
          {USERS.map((u: AppUser) => (
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
              {u.display_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
