'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import * as ROSLIB from 'roslib';
import { useRobotConnection } from '@/contexts/RobotConnectionContext';
import { useRobotProfile } from '@/contexts/RobotProfileContext';
import { getRosTopic } from '@/utils/ros/topics-and-services-v2';
import {
  Play, Square, Trash2, Plus, GripVertical,
  ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Clock, StopCircle,
  RotateCcw, ChevronUp, ChevronDown,
} from 'lucide-react';
import { cn } from '@/utils/cn';

// ── Block types ─────────────────────────────────────────────────────────── //

type BlockType = 'forward' | 'backward' | 'turn_left' | 'turn_right' | 'wait' | 'stop';

interface Block {
  id: string;
  type: BlockType;
  duration: number;   // seconds
  speed: number;      // m/s or rad/s
}

const BLOCK_DEFS: Record<BlockType, {
  label: string;
  color: string;
  darkColor: string;
  icon: React.ComponentType<{ className?: string }>;
  defaultDuration: number;
  defaultSpeed: number;
  unit: string;
  hasSpeed: boolean;
}> = {
  forward:    { label: 'Move Forward',  color: 'bg-green-100 border-green-400',   darkColor: 'dark:bg-green-900/30 dark:border-green-600',  icon: ArrowUp,     defaultDuration: 1.0, defaultSpeed: 0.3, unit: 'm/s',   hasSpeed: true  },
  backward:   { label: 'Move Backward', color: 'bg-blue-100 border-blue-400',     darkColor: 'dark:bg-blue-900/30 dark:border-blue-600',    icon: ArrowDown,   defaultDuration: 1.0, defaultSpeed: 0.2, unit: 'm/s',   hasSpeed: true  },
  turn_left:  { label: 'Turn Left',     color: 'bg-yellow-100 border-yellow-400', darkColor: 'dark:bg-yellow-900/30 dark:border-yellow-600',icon: ArrowLeft,   defaultDuration: 1.0, defaultSpeed: 0.8, unit: 'rad/s', hasSpeed: true  },
  turn_right: { label: 'Turn Right',    color: 'bg-orange-100 border-orange-400', darkColor: 'dark:bg-orange-900/30 dark:border-orange-600',icon: ArrowRight,  defaultDuration: 1.0, defaultSpeed: 0.8, unit: 'rad/s', hasSpeed: true  },
  wait:       { label: 'Wait',          color: 'bg-purple-100 border-purple-400', darkColor: 'dark:bg-purple-900/30 dark:border-purple-600',icon: Clock,       defaultDuration: 1.0, defaultSpeed: 0,   unit: 's',     hasSpeed: false },
  stop:       { label: 'Stop',          color: 'bg-red-100 border-red-400',       darkColor: 'dark:bg-red-900/30 dark:border-red-600',      icon: StopCircle,  defaultDuration: 0,   defaultSpeed: 0,   unit: '',      hasSpeed: false },
};

const PALETTE_ORDER: BlockType[] = ['forward', 'backward', 'turn_left', 'turn_right', 'wait', 'stop'];

let _uid = 0;
function uid() { return `b${++_uid}`; }

// ── Component ────────────────────────────────────────────────────────────── //

export default function BlockProgrammingPage() {
  const { connection } = useRobotConnection();
  const { currentProfile } = useRobotProfile();
  const cmdVelTopic = useRef<ROSLIB.Topic<Record<string, unknown>> | null>(null);

  const [blocks, setBlocks] = useState<Block[]>([]);
  const [running, setRunning] = useState(false);
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState<number | null>(null);
  const cancelRef = useRef(false);

  useEffect(() => {
    document.title = 'Block Programming - BotBot';
  }, []);

  // Connect cmd_vel publisher
  useEffect(() => {
    if (!connection.ros || !connection.online) {
      cmdVelTopic.current = null;
      return;
    }
    const topicName = getRosTopic('velocityNipple', currentProfile);
    cmdVelTopic.current = new ROSLIB.Topic({
      ros: connection.ros,
      name: topicName,
      messageType: 'geometry_msgs/Twist',
    });
  }, [connection.ros, connection.online, currentProfile]);

  // ── Publish helper ─────────────────────────────────────────────────────── //
  const publish = useCallback((linear: number, angular: number) => {
    if (!cmdVelTopic.current) return;
    cmdVelTopic.current.publish({
      linear: { x: linear, y: 0, z: 0 },
      angular: { x: 0, y: 0, z: angular },
    } as Record<string, unknown>);
  }, []);

  const stop = useCallback(() => publish(0, 0), [publish]);

  // ── Run program ────────────────────────────────────────────────────────── //
  const runProgram = async () => {
    if (running || blocks.length === 0) return;
    setRunning(true);
    cancelRef.current = false;

    for (let i = 0; i < blocks.length; i++) {
      if (cancelRef.current) break;
      const block = blocks[i];
      setActiveIdx(i);
      const def = BLOCK_DEFS[block.type];

      switch (block.type) {
        case 'forward':
          publish(block.speed, 0);
          await sleep(block.duration * 1000, cancelRef);
          stop();
          break;
        case 'backward':
          publish(-block.speed, 0);
          await sleep(block.duration * 1000, cancelRef);
          stop();
          break;
        case 'turn_left':
          publish(0, block.speed);
          await sleep(block.duration * 1000, cancelRef);
          stop();
          break;
        case 'turn_right':
          publish(0, -block.speed);
          await sleep(block.duration * 1000, cancelRef);
          stop();
          break;
        case 'wait':
          await sleep(block.duration * 1000, cancelRef);
          break;
        case 'stop':
          stop();
          await sleep(200, cancelRef);
          break;
      }

      if (cancelRef.current) break;
    }

    stop();
    setActiveIdx(null);
    setRunning(false);
  };

  const cancelProgram = () => {
    cancelRef.current = true;
    stop();
  };

  // ── Block editing ─────────────────────────────────────────────────────── //
  const addBlock = (type: BlockType) => {
    const def = BLOCK_DEFS[type];
    setBlocks(prev => [...prev, { id: uid(), type, duration: def.defaultDuration, speed: def.defaultSpeed }]);
  };

  const removeBlock = (id: string) => setBlocks(prev => prev.filter(b => b.id !== id));

  const moveBlock = (id: string, dir: -1 | 1) => {
    setBlocks(prev => {
      const idx = prev.findIndex(b => b.id === id);
      if (idx < 0) return prev;
      const next = idx + dir;
      if (next < 0 || next >= prev.length) return prev;
      const arr = [...prev];
      [arr[idx], arr[next]] = [arr[next], arr[idx]];
      return arr;
    });
  };

  const updateBlock = (id: string, field: 'duration' | 'speed', value: number) => {
    setBlocks(prev => prev.map(b => b.id === id ? { ...b, [field]: value } : b));
  };

  // ── Drag and drop ─────────────────────────────────────────────────────── //
  const dragId = useRef<string | null>(null);

  const onDragStart = (id: string) => { dragId.current = id; };
  const onDragOver = (e: React.DragEvent, idx: number) => { e.preventDefault(); setDragOver(idx); };
  const onDrop = (e: React.DragEvent, targetIdx: number) => {
    e.preventDefault();
    setDragOver(null);
    if (!dragId.current) return;
    const fromIdx = blocks.findIndex(b => b.id === dragId.current);
    if (fromIdx < 0 || fromIdx === targetIdx) return;
    const arr = [...blocks];
    const [moved] = arr.splice(fromIdx, 1);
    arr.splice(targetIdx, 0, moved);
    setBlocks(arr);
    dragId.current = null;
  };

  return (
    <div className="w-full h-[calc(100vh-56px-24px)] flex gap-3 px-1 pt-2 overflow-hidden">

      {/* ── Palette ─────────────────────────────────────────────────────── */}
      <div className="w-44 flex-shrink-0 flex flex-col gap-2">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider px-1">Blocks</h2>
        {PALETTE_ORDER.map(type => {
          const def = BLOCK_DEFS[type];
          const Icon = def.icon;
          return (
            <button
              key={type}
              onClick={() => addBlock(type)}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg border-2 text-sm font-medium',
                'hover:scale-105 active:scale-95 transition-transform cursor-pointer text-left',
                def.color, def.darkColor
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">{def.label}</span>
            </button>
          );
        })}
        <p className="text-xs text-gray-400 px-1 mt-2">Click to add → sequence</p>
      </div>

      {/* ── Sequence ─────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Toolbar */}
        <div className="flex items-center gap-2 mb-2">
          <button
            onClick={running ? cancelProgram : runProgram}
            disabled={blocks.length === 0}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors',
              running
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-green-500 hover:bg-green-600 text-white disabled:opacity-40 disabled:cursor-not-allowed'
            )}
          >
            {running ? <><Square className="w-4 h-4" />Stop</> : <><Play className="w-4 h-4" />Run</>}
          </button>
          <button
            onClick={() => { setBlocks([]); setActiveIdx(null); }}
            disabled={running}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-botbot-darker text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-botbot-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <RotateCcw className="w-4 h-4" />Clear
          </button>
          {!connection.online && (
            <span className="text-xs text-orange-500 font-medium bg-orange-50 dark:bg-orange-900/20 px-2 py-1 rounded">
              Robot offline — commands won&apos;t send
            </span>
          )}
          {blocks.length > 0 && (
            <span className="text-xs text-gray-400 ml-auto">{blocks.length} block{blocks.length !== 1 ? 's' : ''}</span>
          )}
        </div>

        {/* Block list */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {blocks.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-3">
              <Plus className="w-10 h-10 opacity-30" />
              <p className="text-sm">Click blocks on the left to build your program</p>
            </div>
          )}

          {blocks.map((block, idx) => {
            const def = BLOCK_DEFS[block.type];
            const Icon = def.icon;
            const isActive = activeIdx === idx;
            return (
              <div
                key={block.id}
                draggable
                onDragStart={() => onDragStart(block.id)}
                onDragOver={e => onDragOver(e, idx)}
                onDrop={e => onDrop(e, idx)}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg border-2 text-sm transition-all',
                  def.color, def.darkColor,
                  isActive && 'ring-2 ring-yellow-400 animate-pulse',
                  dragOver === idx && 'opacity-50 scale-95'
                )}
              >
                {/* Drag handle */}
                <GripVertical className="w-4 h-4 text-gray-400 cursor-grab flex-shrink-0" />

                {/* Step number */}
                <span className="text-xs font-bold text-gray-500 w-5 text-center">{idx + 1}</span>

                {/* Icon + label */}
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="font-medium w-28 flex-shrink-0">{def.label}</span>

                {/* Duration */}
                {block.type !== 'stop' && (
                  <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                    <span>For</span>
                    <input
                      type="number"
                      min={0.1}
                      max={30}
                      step={0.1}
                      value={block.duration}
                      onChange={e => updateBlock(block.id, 'duration', parseFloat(e.target.value) || 0.1)}
                      disabled={running}
                      className="w-14 px-1 py-0.5 border rounded text-center bg-white dark:bg-botbot-dark dark:border-gray-600 disabled:opacity-50"
                    />
                    <span>s</span>
                  </label>
                )}

                {/* Speed */}
                {def.hasSpeed && (
                  <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                    <span>@</span>
                    <input
                      type="number"
                      min={0.05}
                      max={2}
                      step={0.05}
                      value={block.speed}
                      onChange={e => updateBlock(block.id, 'speed', parseFloat(e.target.value) || 0.1)}
                      disabled={running}
                      className="w-14 px-1 py-0.5 border rounded text-center bg-white dark:bg-botbot-dark dark:border-gray-600 disabled:opacity-50"
                    />
                    <span>{def.unit}</span>
                  </label>
                )}

                {/* Move up/down */}
                <div className="flex flex-col ml-auto flex-shrink-0">
                  <button
                    onClick={() => moveBlock(block.id, -1)}
                    disabled={running || idx === 0}
                    className="p-0.5 hover:text-primary disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronUp className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => moveBlock(block.id, 1)}
                    disabled={running || idx === blocks.length - 1}
                    className="p-0.5 hover:text-primary disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronDown className="w-3 h-3" />
                  </button>
                </div>

                {/* Delete */}
                <button
                  onClick={() => removeBlock(block.id)}
                  disabled={running}
                  className="flex-shrink-0 hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Utility ──────────────────────────────────────────────────────────────── //
function sleep(ms: number, cancel: React.MutableRefObject<boolean>): Promise<void> {
  return new Promise(resolve => {
    const start = Date.now();
    function tick() {
      if (cancel.current || Date.now() - start >= ms) {
        resolve();
      } else {
        requestAnimationFrame(tick);
      }
    }
    tick();
  });
}
