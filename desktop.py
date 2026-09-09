from __future__ import annotations
import copy
import json
import os
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import asyncio
from audio_core import NARRATOR, DEFAULT_VOICE, parse_srt, recognize, export_audio, synthesize, effective_voice
from text_srt import read_text, text_to_cues, to_srt

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('声幕 · SRT Voice Studio')
        self.geometry('1380x880'); self.minsize(1200,720)
        self.cues, self.cast = [], {NARRATOR:dict(enabled=True, voice=DEFAULT_VOICE)}
        self.voices = [DEFAULT_VOICE,'zh-CN-YunxiNeural','zh-CN-YunjianNeural','zh-CN-XiaoyiNeural','en-US-AriaNeural','en-US-GuyNeural']
        self.events, self.cancel = queue.Queue(), threading.Event()
        self.busy = False
        self.preview_dir = tempfile.TemporaryDirectory(prefix='srt-preview-')
        self.vars = {k:tk.StringVar(value=v) for k,v in {
            'engine':'Edge TTS','rate':'0','timing':'连续朗读 / Continuous',
            'base':'https://api.deepseek.com/v1','model':'deepseek-chat','key':'',
            'tts_base':'','tts_model':'','tts_key':'', 'filter':'zh-',
        }.items()}
        self.status = tk.StringVar(value='导入 SRT / TXT → AI 识别 → 分配声音 → 导出 / Import → Identify → Cast → Export')
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10))
        style.configure('Treeview', rowheight=30)
        top = ttk.Frame(self,padding=14); top.pack(fill='x')
        ttk.Label(top,text='声幕 / Voice Studio',font=('Microsoft YaHei UI',18,'bold')).pack(side='left')
        for label,command in [('导入 SRT / Import',self.import_srt),('打开工程 / Open',self.load_project),('保存工程 / Save',self.save_project),('AI / 引擎设置 / Settings',self.settings)]:
            ttk.Button(top,text=label,command=command).pack(side='right',padx=4)
        text_tools = ttk.Frame(self,padding=(14,0,14,8)); text_tools.pack(fill='x')
        ttk.Button(text_tools,text='TXT / 文字转 SRT · Text to SRT',command=self.text_dialog).pack(side='left',padx=4)
        ttk.Button(text_tools,text='导出 SRT / Export SRT',command=self.export_srt).pack(side='left',padx=4)
        self.include_speakers = tk.BooleanVar(value=False)
        ttk.Checkbutton(text_tools,text='SRT 包含人物标记 / Include speaker labels',variable=self.include_speakers).pack(side='left',padx=10)
        controls = ttk.Frame(self,padding=(14,0,14,10)); controls.pack(fill='x')
        ttk.Label(controls,text='引擎 / Engine').pack(side='left')
        engine = ttk.Combobox(controls,textvariable=self.vars['engine'],values=['Edge TTS','兼容 TTS API / Compatible'],state='readonly',width=24)
        engine.pack(side='left',padx=6); engine.bind('<<ComboboxSelected>>',self.change_engine)
        ttk.Button(controls,text='AI 识别人物 / Identify',command=self.analyze).pack(side='left',padx=5)
        ttk.Button(controls,text='添加人物 / Add',command=self.add_actor).pack(side='left',padx=5)
        ttk.Button(controls,text='刷新声音 / Refresh voices',command=self.refresh_voices).pack(side='left',padx=5)
        ttk.Label(controls,text='筛选 / Filter').pack(side='left',padx=(15,4))
        search = ttk.Entry(controls,textvariable=self.vars['filter'],width=15); search.pack(side='left')
        search.bind('<KeyRelease>',lambda e:self.render_cast())
        self.tabs = ttk.Notebook(self); self.tabs.pack(fill='both',expand=True,padx=14)
        table_page = ttk.Frame(self.tabs); self.tabs.add(table_page,text='字幕校正 / Subtitles')
        self.tree = ttk.Treeview(table_page,columns=('id','time','speaker','voice','text'),show='headings',selectmode='extended')
        for key,title,width in [('id','行 / #',45),('time','时间 / Time (s)',145),('speaker','人物 / Speaker',110),('voice','实际声音 / Voice',230),('text','文本（双击编辑） / Text (double-click to edit)',500)]:
            self.tree.heading(key,text=title); self.tree.column(key,width=width,stretch=key=='text')
        scroll = ttk.Scrollbar(table_page,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); self.tree.pack(fill='both',expand=True)
        self.tree.bind('<Double-1>',self.edit_line)
        actor_page = ttk.Frame(self.tabs); self.tabs.add(actor_page,text='人物与声音 / Cast & voices')
        ttk.Label(actor_page,text='勾选人物独立配音，其余使用画外音。 / Enable individual voices; unchecked characters use Narrator. Enter a full voice ID if needed.',padding=10).pack(anchor='w')
        canvas = tk.Canvas(actor_page,highlightthickness=0)
        bar = ttk.Scrollbar(actor_page,command=canvas.yview); bar.pack(side='right',fill='y')
        canvas.pack(fill='both',expand=True); canvas.configure(yscrollcommand=bar.set)
        self.actor_frame = ttk.Frame(canvas,padding=10)
        window = canvas.create_window((0,0),window=self.actor_frame,anchor='nw')
        self.actor_frame.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        editing = ttk.Frame(self,padding=10); editing.pack(fill='x')
        ttk.Label(editing,text='选中字幕分配给 / Assign selected to').pack(side='left')
        self.assign = ttk.Combobox(editing,values=[NARRATOR],state='readonly',width=20); self.assign.set(NARRATOR); self.assign.pack(side='left',padx=5)
        ttk.Button(editing,text='批量分配 / Assign',command=self.assign_lines).pack(side='left')
        ttk.Button(editing,text='试听第一句 / Preview first',command=self.preview_line).pack(side='left',padx=8)
        bottom = ttk.Frame(self,padding=10); bottom.pack(fill='x')
        ttk.Label(bottom,text='语速 / Rate %').pack(side='left')
        ttk.Spinbox(bottom,from_=-50,to=100,textvariable=self.vars['rate'],width=5).pack(side='left',padx=5)
        ttk.Combobox(bottom,textvariable=self.vars['timing'],values=['连续朗读 / Continuous','按字幕起点（超长顺延） / Subtitle timing'],state='readonly',width=44).pack(side='left',padx=10)
        ttk.Button(bottom,text='导出 / Export MP3 / WAV',command=self.export).pack(side='right',padx=4)
        ttk.Button(bottom,text='取消任务 / Cancel',command=self.cancel.set).pack(side='right',padx=4)
        ttk.Label(self,textvariable=self.status,padding=10,wraplength=1150).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(100,self.poll); self.render()

    def config(self):
        data = {k:v.get().strip() for k,v in self.vars.items()}
        data['timing'] = data['timing'].split(' / ')[0]
        data['rate'] = int(data['rate'])
        if not -50 <= data['rate'] <= 100: raise ValueError('语速应在 -50 至 100 之间。 / Rate must be between -50 and 100.')
        if data['engine'] != 'Edge TTS' and not all(data[k] for k in ('tts_base','tts_model')):
            raise ValueError('请先配置 TTS 接口地址和模型。 / Configure the TTS base URL and model first.')
        return data

    def idle(self):
        if self.busy:
            messagebox.showinfo('任务进行中 / Busy','请等待当前任务完成，或先取消。 / Wait for the current task or cancel it.'); return False
        return True

    def run(self,work,done):
        if not self.idle(): return
        self.busy = True; self.cancel.clear(); self.status.set('正在处理 / Working…')
        def thread():
            try: self.events.put(('done',(done,work())))
            except Exception as error: self.events.put(('error',str(error) or type(error).__name__))
        threading.Thread(target=thread,daemon=True).start()

    def progress(self,text): self.events.put(('progress',text))

    def poll(self):
        try:
            while True:
                kind,value = self.events.get_nowait()
                if kind == 'progress': self.status.set(value)
                else:
                    self.busy = False
                    if kind == 'error':
                        self.status.set(value)
                        if not value.startswith('已取消'): messagebox.showerror('任务失败 / Task failed',value)
                    elif self.cancel.is_set(): self.status.set('已取消 / Cancelled')
                    else: value[0](value[1])
        except queue.Empty: pass
        self.after(100,self.poll)

    def import_srt(self):
        if not self.idle(): return
        path = filedialog.askopenfilename(filetypes=[('SRT 字幕 / Subtitles','*.srt')])
        if not path: return
        try:
            source = read_text(path)
            cues = parse_srt(source)
            self.cues = cues; self.cast = {NARRATOR:dict(enabled=True,voice=DEFAULT_VOICE if self.vars['engine'].get()=='Edge TTS' else 'alloy')}
            self.ensure_cast(); self.render()
            self.status.set(f'已导入 / Imported {len(cues)} 条字幕 / cues. 无标记归画外音 / Unlabeled lines use Narrator.')
        except Exception as error: messagebox.showerror('导入失败 / Import failed',str(error))

    def text_dialog(self):
        if not self.idle(): return
        win = tk.Toplevel(self); win.title('文字转 SRT / Text to SRT')
        win.geometry('860x620'); win.minsize(740,520); win.grab_set()
        ttk.Label(win,text='粘贴文字或导入 TXT，按句子自动分段。 / Paste text or import TXT; split into sentences.',padding=12).pack(anchor='w')
        box = tk.Text(win,wrap='word',font=('Microsoft YaHei UI',11),undo=True)
        box.pack(fill='both',expand=True,padx=12,pady=6)
        options = ttk.Frame(win,padding=12); options.pack(fill='x')
        duration = tk.StringVar()
        ttk.Label(options,text='总时长（可留空） / Total duration (optional)').pack(side='left')
        ttk.Entry(options,textvariable=duration,width=18).pack(side='left',padx=10)
        ttk.Label(win,text='输入秒数或 MM:SS / HH:MM:SS；留空按阅读速度估算。\nEnter seconds or MM:SS / HH:MM:SS; leave blank to estimate from reading speed.\n设定的是字幕时间轴，配音音频不强制压缩到该时长。 / Sets subtitle timing; audio is not forced to this duration.',padding=12).pack(anchor='w')
        buttons = ttk.Frame(win,padding=12); buttons.pack(fill='x')
        def load():
            path = filedialog.askopenfilename(parent=win,filetypes=[('文字 / Text','*.txt')])
            if not path: return
            try:
                value = read_text(path); box.delete('1.0','end'); box.insert('1.0',value)
            except Exception as error: messagebox.showerror('导入失败 / Import failed',str(error),parent=win)
        def convert():
            try: cues = text_to_cues(box.get('1.0','end'),duration.get())
            except Exception as error:
                messagebox.showerror('转换失败 / Conversion failed',str(error),parent=win); return
            self.cues = cues
            self.cast = {NARRATOR:dict(enabled=True,voice=DEFAULT_VOICE if self.vars['engine'].get()=='Edge TTS' else 'alloy')}
            self.ensure_cast(); self.render(); self.tabs.select(0)
            self.status.set(f'已生成 / Created {len(cues)} 条字幕 / cues · {cues[-1]["end"]/1000:.3f} 秒 / seconds')
            win.destroy()
        ttk.Button(buttons,text='导入 TXT / Import TXT',command=load).pack(side='left')
        ttk.Button(buttons,text='生成字幕 / Create subtitles',command=convert).pack(side='right')

    def export_srt(self):
        if not self.idle(): return
        try: content = to_srt(self.cues,self.include_speakers.get())
        except Exception as error: messagebox.showerror('导出失败 / Export failed',str(error)); return
        path = filedialog.asksaveasfilename(defaultextension='.srt',filetypes=[('SRT 字幕 / Subtitles','*.srt')],initialfile='story.srt')
        if not path: return
        try:
            Path(path).write_text(content,encoding='utf-8-sig')
            self.status.set('SRT 已导出 / SRT exported: '+path)
        except Exception as error: messagebox.showerror('导出失败 / Export failed',str(error))

    def ensure_cast(self):
        for c in self.cues:
            self.cast.setdefault(c['speaker'],dict(enabled=False,voice=self.cast[NARRATOR]['voice']))

    def render(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for i,c in enumerate(self.cues):
            self.tree.insert('', 'end',iid=str(i),values=(c['id'],f'{c["start"]/1000:.3f} → {c["end"]/1000:.3f}',c['speaker'],effective_voice(c['speaker'],self.cast),c['text'].replace('\n',' / ')))
        self.tree.selection_set([i for i in selected if self.tree.exists(i)])
        self.assign['values'] = list(self.cast)
        self.render_cast()

    def render_cast(self):
        for child in self.actor_frame.winfo_children(): child.destroy()
        self.cast_vars = {}
        needle = self.vars['filter'].get().lower()
        voices = [v for v in self.voices if needle in v.lower()] if self.vars['engine'].get()=='Edge TTS' else ['alloy','echo','fable','onyx','nova','shimmer']
        for row,(name,actor) in enumerate(self.cast.items()):
            enabled,voice = tk.BooleanVar(value=actor['enabled']),tk.StringVar(value=actor['voice'])
            self.cast_vars[name] = (enabled,voice)
            check = ttk.Checkbutton(self.actor_frame,text=('画外音 / Narrator' if name == NARRATOR else name),variable=enabled,command=lambda n=name:self.update_actor(n))
            check.grid(row=row,column=0,sticky='w',padx=8,pady=8)
            if name == NARRATOR: check.state(['disabled'])
            ttk.Label(self.actor_frame,text=f'{sum(c["speaker"]==name for c in self.cues)} 句 / lines').grid(row=row,column=1,padx=12)
            combo = ttk.Combobox(self.actor_frame,textvariable=voice,values=voices,width=43)
            combo.grid(row=row,column=2,sticky='ew',padx=8)
            combo.bind('<<ComboboxSelected>>',lambda e,n=name:self.update_actor(n))
            combo.bind('<FocusOut>',lambda e,n=name:self.update_actor(n))
            ttk.Button(self.actor_frame,text='试听 / Preview',command=lambda n=name:self.preview_actor(n)).grid(row=row,column=3,padx=8)
        self.actor_frame.columnconfigure(2,weight=1)

    def update_actor(self,name):
        enabled,voice = self.cast_vars[name]
        self.cast[name] = dict(enabled=True if name==NARRATOR else enabled.get(),voice=voice.get().strip() or self.cast[NARRATOR]['voice'])
        # Update only table values to avoid destroying focused dropdowns.
        for i,c in enumerate(self.cues): self.tree.set(str(i),'voice',effective_voice(c['speaker'],self.cast))

    def add_actor(self):
        if not self.idle(): return
        from tkinter.simpledialog import askstring
        name = askstring('添加人物 / Add','人物名称 / Character name:',parent=self)
        if name and name.strip():
            self.cast.setdefault(name.strip(),dict(enabled=True,voice=self.cast[NARRATOR]['voice'])); self.render()

    def assign_lines(self):
        if not self.idle(): return
        name = self.assign.get()
        if name not in self.cast: return
        for index in self.tree.selection(): self.cues[int(index)]['speaker'] = name
        self.render()

    def edit_line(self,event=None):
        if not self.idle() or not self.tree.selection(): return
        cue = self.cues[int(self.tree.selection()[0])]
        win = tk.Toplevel(self); win.title('修改字幕 / Edit subtitle'); win.geometry('720x340'); win.grab_set()
        text = tk.Text(win,wrap='word',font=('Microsoft YaHei UI',12)); text.pack(fill='both',expand=True,padx=10,pady=10); text.insert('1.0',cue['text'])
        def save():
            value = text.get('1.0','end').strip()
            if not value: return
            cue['text'] = value; win.destroy(); self.render()
        ttk.Button(win,text='保存修改 / Save changes',command=save).pack(pady=8)

    def settings(self):
        if not self.idle(): return
        win = tk.Toplevel(self); win.title('AI 与 TTS 接口设置 / API settings'); win.geometry('860x460'); win.grab_set()
        fields = [('base','AI Base URL（按需含 /v1 / if required）'),('model','AI 模型 / Model'),('key','AI API Key'),('tts_base','TTS Base URL (/audio/speech)'),('tts_model','TTS 模型 / Model'),('tts_key','TTS API Key')]
        for row,(key,label) in enumerate(fields):
            ttk.Label(win,text=label).grid(row=row,column=0,sticky='w',padx=12,pady=10)
            ttk.Entry(win,textvariable=self.vars[key],width=40,show='*' if 'key' in key else '').grid(row=row,column=1,padx=10)
        ttk.Label(win,text='AI 会发送字幕到所填接口；TTS 会发送朗读文本。密钥不写入工程。\nAI sends subtitles to your endpoint; TTS sends spoken text. Keys stay in memory.',wraplength=650).grid(row=6,column=0,columnspan=2,pady=12)
        ttk.Button(win,text='完成 / Done',command=win.destroy).grid(row=7,column=1,pady=8)

    def analyze(self):
        if not self.idle() or not self.cues: return
        config = {k:v.get().strip() for k,v in self.vars.items()}
        if not config['base'] or not config['model']:
            self.settings(); return
        cues = copy.deepcopy(self.cues)
        def done(mapping):
            for c in self.cues: c['speaker'] = mapping[c['id']]
            self.ensure_cast(); self.render(); self.tabs.select(1)
            self.status.set('AI 识别完成，请选择人物并校正。 / Identification complete. Enable characters and review assignments.')
        self.run(lambda:recognize(cues,config,self.cancel,self.progress),done)

    def change_engine(self,event=None):
        if self.busy:
            self.status.set('引擎修改将在下一次任务生效。 / Engine changes apply to the next task.')
        voice = DEFAULT_VOICE if self.vars['engine'].get()=='Edge TTS' else 'alloy'
        for actor in self.cast.values(): actor['voice'] = voice
        self.render()

    def refresh_voices(self):
        async def load():
            import edge_tts
            return await asyncio.wait_for(edge_tts.list_voices(),45)
        def done(voices):
            self.voices = sorted(v['ShortName'] for v in voices); self.render_cast()
            self.status.set(f'已加载 / Loaded {len(self.voices)} Edge voices. 输入 zh- / en- 筛选 / Filter by locale.')
        self.run(lambda:asyncio.run(load()),done)

    def preview_actor(self,name):
        self.update_actor(name)
        self.preview('你好，这是这个角色的配音试听。',self.cast[name]['voice'])

    def preview_line(self):
        if not self.tree.selection(): return
        c = self.cues[int(self.tree.selection()[0])]
        self.preview(c['text'],effective_voice(c['speaker'],self.cast))

    def preview(self,text,voice):
        try: config = self.config()
        except Exception as error: messagebox.showerror('设置错误 / Invalid settings',str(error)); return
        import uuid
        path = Path(self.preview_dir.name)/(uuid.uuid4().hex+'.mp3')
        def done(_):
            os.startfile(str(path)); self.status.set('已在默认播放器打开试听。 / Preview opened in the default player.')
        self.run(lambda:synthesize(text,voice,path,config,self.cancel),done)

    def export(self):
        if not self.idle() or not self.cues: return
        try: config = self.config()
        except Exception as error: messagebox.showerror('设置错误 / Invalid settings',str(error)); return
        path = filedialog.asksaveasfilename(defaultextension='.mp3',filetypes=[('MP3 音频 / Audio','*.mp3'),('WAV 音频 / Audio','*.wav')],initialfile='故事配音.mp3')
        if not path: return
        cues,cast = copy.deepcopy(self.cues),copy.deepcopy(self.cast)
        def done(path): self.status.set('已导出 / Exported: '+path); messagebox.showinfo('导出完成 / Export complete',path)
        self.run(lambda:export_audio(cues,cast,config,path,self.cancel,self.progress),done)

    def save_project(self):
        if not self.idle(): return
        path = filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('配音工程 / Project','*.json')])
        if not path: return
        data = dict(version=1,cues=self.cues,cast=self.cast,settings={k:v.get() for k,v in self.vars.items() if 'key' not in k})
        try: Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); self.status.set('工程已保存（不含密钥） / Project saved (without API keys)')
        except Exception as error: messagebox.showerror('保存失败 / Save failed',str(error))

    def load_project(self):
        if not self.idle(): return
        path = filedialog.askopenfilename(filetypes=[('配音工程 / Project','*.json')])
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            assert data['version']==1 and isinstance(data['cues'],list) and isinstance(data['cast'],dict)
            assert NARRATOR in data['cast']
            ids = set()
            for cue in data['cues']:
                assert type(cue['id']) is int and cue['id'] not in ids
                ids.add(cue['id'])
                assert isinstance(cue['text'],str) and cue['text'].strip() and isinstance(cue['speaker'],str)
                assert type(cue['start']) is int and type(cue['end']) is int and 0<=cue['start']<cue['end']
            for name,actor in data['cast'].items():
                assert isinstance(name,str) and type(actor['enabled']) is bool and isinstance(actor['voice'],str) and actor['voice']
            settings = data.get('settings',{})
            assert isinstance(settings,dict) and all(isinstance(v,str) for v in settings.values())
            self.cues,self.cast = data['cues'],data['cast']; self.cast[NARRATOR]['enabled']=True
            for k,v in settings.items():
                if k in self.vars and 'key' not in k:
                    if k == 'timing': v = {'连续朗读':'连续朗读 / Continuous','按字幕起点（超长顺延）':'按字幕起点（超长顺延） / Subtitle timing'}.get(v,v)
                    if k == 'engine' and v == '兼容 TTS API': v = '兼容 TTS API / Compatible'
                    self.vars[k].set(v)
            self.ensure_cast(); self.render(); self.status.set('工程已恢复，请重新输入密钥。 / Project loaded; re-enter API keys.')
        except Exception as error: messagebox.showerror('工程无效 / Invalid project','文件格式或数据不正确 / Invalid format or data: '+str(error))

    def close(self):
        self.cancel.set()
        self.destroy()

if __name__ == '__main__':
    import sys
    if '--smoke-test' in sys.argv:
        app = App(); app.update(); app.destroy()
    else: App().mainloop()
