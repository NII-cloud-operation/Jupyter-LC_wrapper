import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { INotebookModel, NotebookPanel, NotebookActions } from '@jupyterlab/notebook';
import { DocumentRegistry } from '@jupyterlab/docregistry';
import { IDisposable } from '@lumino/disposable';
import { ICellModel, Cell } from '@jupyterlab/cells';

const plugin: JupyterFrontEndPlugin<void> = {
  id: 'lc_wrapper:plugin',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.debug('JupyterLab extension lc_wrapper is activated!');

    app.docRegistry.addWidgetExtension('Notebook', new LCWrapperExtension());
  }
};

class LCWrapperExtension
  implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel>
{
  createNew(
    panel: NotebookPanel,
    context: DocumentRegistry.IContext<INotebookModel>
  ): IDisposable {
    NotebookActions.executionScheduled.connect((_, args) => {
      if (args.notebook !== panel.content) {
        return;
      }
      const cell = args.cell as Cell;
      prepareExecutionMetadata(cell.model, panel, context);
    });

    panel.sessionContext.kernelChanged.connect(() => {
      const kernel = panel.sessionContext.session?.kernel;
      if (!kernel) {
        return;
      }
      kernel.anyMessage.connect((_, args) => {
        const msg = args.msg;
        if (msg.channel === 'shell' && msg.header.msg_type === 'execute_reply') {
          const content = msg.content as { lc_wrapper: LCWrapperExecuteReply };
          const lcWrapper = content.lc_wrapper;
          const cell = findCellById(panel, lcWrapper.cellId);
          recordLogPath(cell, lcWrapper.log_path);
        }
      });
    });

    return {
      dispose: () => {},
      isDisposed: false
    };
  }
}

function prepareExecutionMetadata(
  cellModel: ICellModel,
  panel: NotebookPanel,
  context: DocumentRegistry.IContext<INotebookModel>
): void {
  const lcCellMeme = cellModel.getMetadata('lc_cell_meme') as LCMeme | undefined;
  const lcNotebookMeme = panel.model?.getMetadata('lc_notebook_meme') as LCMeme | undefined;
  const notebookPath = context.path;

  const lastExecution: LCWrapperLastExecution = {
    lc_current_cell_meme: lcCellMeme?.current,
    lc_current_notebook_meme: lcNotebookMeme?.current,
    notebook_path: notebookPath
  };

  const lcMeta = cellModel.getMetadata('lc_wrapper') as LCWrapperMetadata | undefined;
  cellModel.setMetadata('lc_wrapper', {
    ...lcMeta,
    last_execution: lastExecution
  });
}

function findCellById(
  panel: NotebookPanel,
  cellId: string
): ICellModel {
  for (const cell of panel.content.widgets) {
    if (cell.model.id === cellId) {
      return cell.model;
    }
  }
  throw new Error(`Cell not found: ${cellId}`);
}

interface LCMeme {
  current?: string;
}

interface LCWrapperMetadata {
  log_history?: string[];
  last_execution?: LCWrapperLastExecution;
}

interface LCWrapperLastExecution {
  lc_current_cell_meme?: string;
  lc_current_notebook_meme?: string;
  notebook_path?: string;
}

interface LCWrapperExecuteReply {
  log_path: string;
  cellId: string;
}

function recordLogPath(cellModel: ICellModel, logPath: string): void {
  const lcMeta = cellModel.getMetadata('lc_wrapper') as LCWrapperMetadata | undefined;
  const logHistory = lcMeta?.log_history ?? [];
  cellModel.setMetadata('lc_wrapper', {
    ...lcMeta,
    log_history: [...logHistory, logPath]
  });
  console.debug('[lc_wrapper] Recorded log path:', logPath);
}

export default plugin;
